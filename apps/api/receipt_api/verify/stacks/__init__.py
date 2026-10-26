from pathlib import Path
from typing import Optional

from receipt_api.verify.stacks.base import StackAdapter, TestResult, TestStatus
from receipt_api.verify.stacks.node import NodeStackAdapter
from receipt_api.verify.stacks.python import PythonStackAdapter

AVAILABLE_STACKS: list[StackAdapter] = [
    PythonStackAdapter(),
    NodeStackAdapter(),
]


def detect_stack(repo_path: Path) -> Optional[StackAdapter]:
    """Detect and return the appropriate stack adapter for the repository."""
    for stack in AVAILABLE_STACKS:
        if stack.detect(repo_path):
            return stack
    return None


__all__ = [
    "StackAdapter",
    "TestResult",
    "TestStatus",
    "PythonStackAdapter",
    "NodeStackAdapter",
    "detect_stack",
]
