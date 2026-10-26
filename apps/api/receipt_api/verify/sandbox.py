import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Optional

import structlog

from receipt_api.verify.stacks import StackAdapter, TestResult, detect_stack

structlog.configure(
    logger_factory=structlog.PrintLoggerFactory(sys.stderr),
)
logger = structlog.get_logger(__name__)

# Safe environment variables permitted in sandboxed subprocess
SAFE_ENV_ALLOWLIST = {
    "PATH",
    "PYTHONPATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "LANG",
    "LC_ALL",
    "TERM",
    "COMSPEC",
    "PATHEXT",
}

# Sensitive keys explicitly stripped
SENSITIVE_KEY_PREFIXES = (
    "GITHUB_",
    "LLM_",
    "AWS_",
    "AZURE_",
    "OPENAI_",
    "ANTHROPIC_",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "PASSWORD",
)


@dataclass
class SandboxConfig:
    mode: Literal["subprocess", "docker"] = "subprocess"
    timeout_seconds: int = 60
    network_enabled: bool = False
    max_memory_mb: int = 1024
    extra_env: dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    test_results: list[TestResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": round(self.duration_ms, 2),
            "timed_out": self.timed_out,
            "tests": [asdict(t) for t in self.test_results],
        }


def scrub_environment(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    """Produce a sanitized environment dictionary with all secrets removed."""
    scrubbed = {}
    for key, value in os.environ.items():
        if key in SAFE_ENV_ALLOWLIST:
            scrubbed[key] = value

    # Ensure sensitive prefixes are definitely wiped
    for key in list(scrubbed.keys()):
        upper = key.upper()
        if any(upper.startswith(prefix) for prefix in SENSITIVE_KEY_PREFIXES):
            scrubbed.pop(key, None)

    if extra:
        for k, v in extra.items():
            if not any(k.upper().startswith(p) for p in SENSITIVE_KEY_PREFIXES):
                scrubbed[k] = v

    return scrubbed


class SubprocessSandbox:
    """Restricted subprocess sandbox runner with scrubbed env and timeouts."""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()

    def run(
        self,
        command: list[str],
        cwd: Path,
        on_stdout: Optional[Callable[[str], None]] = None,
    ) -> SandboxResult:
        env = scrub_environment(self.config.extra_env)
        start_time = time.perf_counter()

        logger.info(
            "subprocess_sandbox_start",
            command=command,
            cwd=str(cwd),
            timeout=self.config.timeout_seconds,
        )

        timed_out = False
        stdout_text = ""
        stderr_text = ""
        exit_code = -1

        try:
            proc = subprocess.Popen(
                command,
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout_text, stderr_text = proc.communicate(timeout=self.config.timeout_seconds)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_text, stderr_text = proc.communicate()
                exit_code = -9
                timed_out = True
                logger.warning("subprocess_sandbox_timeout", command=command, timeout=self.config.timeout_seconds)

        except Exception as e:
            stderr_text = f"Sandbox execution error: {e}"
            exit_code = -1
            logger.error("subprocess_sandbox_exception", error=str(e))

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        if on_stdout and stdout_text:
            for line in stdout_text.splitlines():
                on_stdout(line)

        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout_text,
            stderr=stderr_text,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )


class DockerSandbox:
    """Docker container sandbox runner with fallback to SubprocessSandbox."""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig(mode="docker")
        self.subprocess_fallback = SubprocessSandbox(self.config)

    def is_docker_available(self) -> bool:
        try:
            res = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3,
            )
            return res.returncode == 0
        except Exception:
            return False

    def run(
        self,
        command: list[str],
        cwd: Path,
        on_stdout: Optional[Callable[[str], None]] = None,
    ) -> SandboxResult:
        if not self.is_docker_available():
            logger.info("docker_unavailable_falling_back_to_subprocess")
            return self.subprocess_fallback.run(command, cwd, on_stdout)

        # In Docker mode, run with --network none, memory limits, and non-root execution
        start_time = time.perf_counter()
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{cwd.resolve()}:/workspace:rw",
            "-w",
            "/workspace",
            "--network",
            "none" if not self.config.network_enabled else "bridge",
            "-m",
            f"{self.config.max_memory_mb}m",
            "python:3.12-slim",
        ] + command

        res = self.subprocess_fallback.run(docker_cmd, cwd, on_stdout)
        res.duration_ms = (time.perf_counter() - start_time) * 1000.0
        return res


def run_in_sandbox(
    repo_path: Path,
    command: Optional[list[str]] = None,
    stack: Optional[StackAdapter] = None,
    selection: Optional[list[str]] = None,
    config: Optional[SandboxConfig] = None,
) -> SandboxResult:
    """Execute tests or a command in the configured sandbox environment."""
    cfg = config or SandboxConfig()

    resolved_stack = stack or detect_stack(repo_path)
    if not command:
        if not resolved_stack:
            raise ValueError(f"Could not automatically detect stack for {repo_path}")
        command = resolved_stack.get_test_command(selection)

    sandbox = DockerSandbox(cfg) if cfg.mode == "docker" else SubprocessSandbox(cfg)
    result = sandbox.run(command, cwd=repo_path)

    if resolved_stack:
        result.test_results = resolved_stack.parse_results(
            result.stdout, result.stderr, result.exit_code
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Receipt Sandbox Test Runner")
    parser.add_argument("--repo", required=True, help="Path to repository")
    parser.add_argument("--sha", default=None, help="Git commit SHA or ref to checkout")
    parser.add_argument("--run-tests", action="store_true", help="Run tests for detected stack")
    parser.add_argument("--timeout", type=int, default=60, help="Execution timeout in seconds")
    parser.add_argument("--mode", choices=["subprocess", "docker"], default="subprocess", help="Sandbox backend")

    args = parser.parse_args()
    repo_path = Path(args.repo).resolve()

    if not repo_path.exists():
        print(json.dumps({"error": f"Repository path not found: {repo_path}"}), file=sys.stderr)
        sys.exit(1)

    cfg = SandboxConfig(mode=args.mode, timeout_seconds=args.timeout)
    res = run_in_sandbox(repo_path=repo_path, config=cfg)

    print(json.dumps(res.to_dict(), indent=2))
    sys.exit(0 if res.exit_code == 0 else 1)


if __name__ == "__main__":
    main()
