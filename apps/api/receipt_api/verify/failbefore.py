from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import structlog
from pydantic import BaseModel, Field

from receipt_api.verify.intent import AcceptanceCriterion
from receipt_api.verify.sandbox import SandboxConfig, run_in_sandbox
from receipt_api.verify.stacks import StackAdapter
from receipt_api.verify.stacks.base import TestStatus

logger = structlog.get_logger(__name__)


class ProofItem(BaseModel):
    criterion_id: str
    test_name: str
    base: Literal["PASS", "FAIL", "ERROR"]
    head: Literal["PASS", "FAIL", "ERROR"]
    vacuous: bool
    artifact_id: Optional[str] = None


def evaluate_fail_before_proof(
    criterion: AcceptanceCriterion,
    test_file_path: Path,
    base_repo_path: Path,
    head_repo_path: Path,
    stack: StackAdapter,
    config: Optional[SandboxConfig] = None,
) -> ProofItem:
    """Run generated test on base and head repos to evaluate non-vacuous proof."""
    test_rel_path = test_file_path.name
    test_name = test_file_path.stem

    # 1. Run test on base repo (if distinct base worktree exists)
    if base_repo_path != head_repo_path:
        base_res = run_in_sandbox(
            repo_path=base_repo_path,
            command=stack.get_test_command(selection=[str(test_file_path)]),
            stack=stack,
            config=config,
        )
        base_passed = any(t.status == TestStatus.PASS for t in base_res.test_results)
        base_status: Literal["PASS", "FAIL", "ERROR"] = "PASS" if base_passed else "FAIL"
    else:
        # Same directory (no distinct base worktree): treat base as not containing the feature/fix
        base_status = "FAIL"

    # 2. Run test on head repo
    head_res = run_in_sandbox(
        repo_path=head_repo_path,
        command=stack.get_test_command(selection=[str(test_file_path)]),
        stack=stack,
        config=config,
    )
    head_passed = any(t.status == TestStatus.PASS for t in head_res.test_results)
    head_status: Literal["PASS", "FAIL", "ERROR"] = "PASS" if head_passed else "FAIL"

    # 3. Vacuous proof check
    # For bugfix and feature, a test that passes on base is vacuous (doesn't prove PR effect)
    vacuous = False
    if criterion.kind in ("bugfix", "feature") and base_repo_path != head_repo_path:
        if base_status == "PASS":
            vacuous = True
    elif criterion.kind == "refactor":
        # For refactors, both base and head should pass to prove behavior preservation
        vacuous = False

    logger.info(
        "fail_before_evaluated",
        criterion_id=criterion.id,
        kind=criterion.kind,
        base=base_status,
        head=head_status,
        vacuous=vacuous,
    )

    return ProofItem(
        criterion_id=criterion.id,
        test_name=test_name,
        base=base_status,
        head=head_status,
        vacuous=vacuous,
    )
