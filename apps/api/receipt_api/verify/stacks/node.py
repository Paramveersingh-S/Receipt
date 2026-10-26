import re
from pathlib import Path
from typing import Optional

from receipt_api.verify.stacks.base import StackAdapter, TestResult, TestStatus


class NodeStackAdapter(StackAdapter):
    """Node / vitest / jest test runner and output parser."""

    @property
    def name(self) -> str:
        return "node"

    def detect(self, repo_path: Path) -> bool:
        return (repo_path / "package.json").exists()

    def get_prepare_command(self) -> Optional[list[str]]:
        return None

    def get_test_command(self, selection: Optional[list[str]] = None) -> list[str]:
        cmd = ["npm", "test", "--", "--reporter=verbose"]
        if selection:
            cmd.extend(selection)
        return cmd

    def parse_results(self, stdout: str, stderr: str, exit_code: int) -> list[TestResult]:
        results: list[TestResult] = []
        combined = stdout + "\n" + stderr

        # Match lines like:
        # √ adds two numbers (2 ms)
        # × subtracts numbers (5 ms)
        # PASS src/calc.test.js
        # FAIL src/calc.test.js
        pass_pattern = re.compile(r"^\s*[√✓✔]\s+(?P<name>.+?)(?:\s+\(\d+\s*ms\))?$", re.MULTILINE)
        fail_pattern = re.compile(r"^\s*[×✗✖]\s+(?P<name>.+?)(?:\s+\(\d+\s*ms\))?$", re.MULTILINE)

        for match in pass_pattern.finditer(combined):
            results.append(
                TestResult(
                    name=match.group("name").strip(),
                    status=TestStatus.PASS,
                )
            )

        for match in fail_pattern.finditer(combined):
            results.append(
                TestResult(
                    name=match.group("name").strip(),
                    status=TestStatus.FAIL,
                )
            )

        # Fallback if no specific test symbols were found
        if not results:
            if exit_code == 0:
                results.append(TestResult(name="node_suite", status=TestStatus.PASS))
            else:
                results.append(
                    TestResult(
                        name="node_suite",
                        status=TestStatus.FAIL,
                        message=(stderr or stdout)[:500].strip(),
                    )
                )

        return results
