import re
import sys
from pathlib import Path
from typing import Optional

from receipt_api.verify.stacks.base import StackAdapter, TestResult, TestStatus


class PythonStackAdapter(StackAdapter):
    """Python / pytest test runner and output parser."""

    @property
    def name(self) -> str:
        return "python"

    def detect(self, repo_path: Path) -> bool:
        indicators = [
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "pytest.ini",
            "Pipfile",
        ]
        if any((repo_path / f).exists() for f in indicators):
            return True

        # Check for any .py files in tests directory
        tests_dir = repo_path / "tests"
        if tests_dir.is_dir() and any(tests_dir.glob("test_*.py")):
            return True

        return False

    def get_prepare_command(self) -> Optional[list[str]]:
        return None

    def get_test_command(self, selection: Optional[list[str]] = None) -> list[str]:
        cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
        if selection:
            cmd.extend(selection)
        return cmd

    def parse_results(self, stdout: str, stderr: str, exit_code: int) -> list[TestResult]:
        results: list[TestResult] = []
        combined = stdout + "\n" + stderr

        # Match pytest verbose lines like:
        # tests/test_calc.py::test_add PASSED [ 33%]
        # tests/test_calc.py::test_subtract FAILED [ 66%]
        # tests/test_calc.py::test_skip SKIPPED [100%]
        # or Windows backslash paths
        pattern = re.compile(
            r"^(?P<path>[\w\.\\/\-_]+)::(?P<name>[\w\-_\.\[\]]+)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED)",
            re.MULTILINE,
        )

        for match in pattern.finditer(combined):
            test_path = match.group("path")
            test_name = match.group("name")
            status_str = match.group("status")

            status = TestStatus.PASS
            if status_str == "FAILED":
                status = TestStatus.FAIL
            elif status_str == "ERROR":
                status = TestStatus.ERROR
            elif status_str == "SKIPPED":
                status = TestStatus.SKIPPED

            results.append(
                TestResult(
                    name=test_name,
                    status=status,
                    file=test_path,
                )
            )

        # Fallback if pytest didn't print per-test lines (e.g. fatal error or collection failure)
        if not results and exit_code != 0:
            results.append(
                TestResult(
                    name="pytest_execution",
                    status=TestStatus.ERROR,
                    message=(stderr or stdout)[:500].strip(),
                )
            )
        elif not results and exit_code == 0:
            # Check summary line like "1 passed in 0.05s"
            if "passed" in combined:
                results.append(
                    TestResult(
                        name="suite_passed",
                        status=TestStatus.PASS,
                    )
                )

        return results
