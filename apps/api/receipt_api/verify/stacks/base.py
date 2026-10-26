from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class TestStatus(str, Enum):
    __test__ = False
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass
class TestResult:
    __test__ = False
    name: str
    status: TestStatus
    duration_ms: float = 0.0
    message: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None


class StackAdapter(ABC):
    """Abstract adapter for stack-specific test preparation, execution, and parsing."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the stack adapter (e.g. 'python', 'node')."""
        pass

    @abstractmethod
    def detect(self, repo_path: Path) -> bool:
        """Return True if this stack applies to the repository."""
        pass

    @abstractmethod
    def get_prepare_command(self) -> Optional[list[str]]:
        """Return shell command to prepare dependencies, or None if already prepared."""
        pass

    @abstractmethod
    def get_test_command(self, selection: Optional[list[str]] = None) -> list[str]:
        """Return command to run tests, optionally filtering by test selection."""
        pass

    @abstractmethod
    def parse_results(self, stdout: str, stderr: str, exit_code: int) -> list[TestResult]:
        """Parse test command output into a normalized list of TestResults."""
        pass
