import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from receipt_api.verify.sandbox import (
    SandboxConfig,
    SubprocessSandbox,
    DockerSandbox,
    run_in_sandbox,
    scrub_environment,
)
from receipt_api.verify.stacks import detect_stack
from receipt_api.verify.stacks.base import TestStatus
from receipt_api.verify.stacks.python import PythonStackAdapter
from receipt_api.verify.stacks.node import NodeStackAdapter

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "repos"


def test_detect_stack():
    py_repo = FIXTURES_DIR / "py_calc"
    node_repo = FIXTURES_DIR / "node_calc"

    py_stack = detect_stack(py_repo)
    assert isinstance(py_stack, PythonStackAdapter)
    assert py_stack.name == "python"

    node_stack = detect_stack(node_repo)
    assert isinstance(node_stack, NodeStackAdapter)
    assert node_stack.name == "node"


def test_subprocess_sandbox_py_calc():
    py_repo = FIXTURES_DIR / "py_calc"
    cfg = SandboxConfig(mode="subprocess", timeout_seconds=15)
    result = run_in_sandbox(repo_path=py_repo, config=cfg)

    assert result.exit_code == 0
    assert result.timed_out is False
    assert len(result.test_results) >= 3

    passed_names = [t.name for t in result.test_results if t.status == TestStatus.PASS]
    assert "test_add" in passed_names
    assert "test_subtract" in passed_names
    assert "test_multiply" in passed_names


def test_sandbox_scrubs_environment():
    # Inject sensitive secrets into host process env
    os.environ["GITHUB_TOKEN"] = "ghp_super_secret_host_token"
    os.environ["LLM_API_KEY"] = "sk-untrusted-leak-token"
    os.environ["SECRET_PASSWORD"] = "do_not_leak_me"

    try:
        scrubbed = scrub_environment()
        assert "GITHUB_TOKEN" not in scrubbed
        assert "LLM_API_KEY" not in scrubbed
        assert "SECRET_PASSWORD" not in scrubbed

        # Execute a Python subprocess inside the sandbox that asserts the secrets are absent
        code = (
            "import os, sys\n"
            "for key in ['GITHUB_TOKEN', 'LLM_API_KEY', 'SECRET_PASSWORD']:\n"
            "    if key in os.environ:\n"
            "        sys.exit(42)\n"
            "sys.exit(0)\n"
        )
        sandbox = SubprocessSandbox(SandboxConfig(timeout_seconds=5))
        py_repo = FIXTURES_DIR / "py_calc"
        res = sandbox.run([sys.executable, "-c", code], cwd=py_repo)
        assert res.exit_code == 0
    finally:
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("LLM_API_KEY", None)
        os.environ.pop("SECRET_PASSWORD", None)


def test_sandbox_timeout_enforcement():
    sandbox = SubprocessSandbox(SandboxConfig(timeout_seconds=1))
    py_repo = FIXTURES_DIR / "py_calc"

    code = "import time; time.sleep(10)"
    res = sandbox.run([sys.executable, "-c", code], cwd=py_repo)

    assert res.timed_out is True
    assert res.exit_code != 0


def test_sandbox_cli_runner():
    py_repo = FIXTURES_DIR / "py_calc"
    cmd = [
        sys.executable,
        "-m",
        "receipt_api.verify.sandbox",
        "--repo",
        str(py_repo),
        "--run-tests",
        "--timeout",
        "15",
    ]
    env = dict(os.environ)
    api_dir = str(Path(__file__).parent.parent / "apps" / "api")
    env["PYTHONPATH"] = f"{api_dir};{env.get('PYTHONPATH', '')}" if os.name == "nt" else f"{api_dir}:{env.get('PYTHONPATH', '')}"

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)

    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["exit_code"] == 0
    assert data["timed_out"] is False
    assert len(data["tests"]) >= 3
