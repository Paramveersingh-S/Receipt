import structlog
from pathlib import Path
from typing import List, Optional
from sqlmodel import Session

from receipt_api.events import emit_event
from receipt_api.repair.patcher import FailureBundle, PatchLLMRepair
from receipt_api.schemas import Receipt, RepairHistoryItem
from receipt_api.verify.pipeline import VerificationPipeline

logger = structlog.get_logger(__name__)


def run_repair_loop(
    repo_path: Path,
    repo_name: str,
    pr_number: int,
    pr_title: str,
    pr_body: str = "",
    base_sha: str = "HEAD~1",
    head_sha: str = "HEAD",
    max_iterations: int = 3,
    session: Optional[Session] = None,
) -> Receipt:
    """Iteratively verify, generate patches, and re-verify until VERIFIED or max iterations reached."""
    repair_history: List[RepairHistoryItem] = []
    patcher = PatchLLMRepair()
    last_score = -1

    current_receipt: Optional[Receipt] = None

    for iteration in range(1, max_iterations + 1):
        logger.info("repair_loop_iteration_start", iteration=iteration, pr=pr_number)

        # 1. Run full verification pipeline for this iteration
        pipeline = VerificationPipeline(
            repo_path=repo_path,
            repo_name=repo_name,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_body=pr_body,
            base_sha=base_sha,
            head_sha=head_sha,
        )
        receipt = pipeline.run(session=session)
        current_receipt = receipt

        # If VERIFIED, we are done!
        if receipt.verdict == "VERIFIED":
            logger.info("repair_loop_succeeded", iteration=iteration, score=receipt.score)
            receipt.repair_history = repair_history
            receipt.iterations = iteration
            return receipt

        # If we reached the final iteration, stop and return the receipt
        if iteration >= max_iterations:
            logger.info("repair_loop_max_iterations_reached", iteration=iteration, score=receipt.score)
            repair_history.append(
                RepairHistoryItem(
                    iteration=iteration,
                    verdict=receipt.verdict,
                    score=receipt.score,
                    failure_summary="; ".join(
                        [c.title for c in receipt.constraints if c.result == "FAIL"][:2]
                    ) or "Verification thresholds unmet",
                    patch_artifact_id=f"ar_patch_{iteration}",
                )
            )
            receipt.repair_history = repair_history
            receipt.iterations = iteration
            return receipt

        # No progress guardrail: if score didn't improve from last iteration, stop early
        if last_score != -1 and receipt.score <= last_score:
            logger.warning("repair_loop_no_progress_stopping", last_score=last_score, current_score=receipt.score)
            repair_history.append(
                RepairHistoryItem(
                    iteration=iteration,
                    verdict=receipt.verdict,
                    score=receipt.score,
                    failure_summary="Score did not improve from prior attempt",
                    patch_artifact_id=f"ar_patch_{iteration}",
                )
            )
            receipt.repair_history = repair_history
            receipt.iterations = iteration
            return receipt

        # Record this iteration's failure into repair_history
        fail_summary = "; ".join(
            [c.title for c in receipt.constraints if c.result == "FAIL"][:2]
        ) or "Proof or test regression failures"

        repair_history.append(
            RepairHistoryItem(
                iteration=iteration,
                verdict=receipt.verdict,
                score=receipt.score,
                failure_summary=fail_summary,
                patch_artifact_id=f"ar_patch_{iteration}",
            )
        )
        last_score = receipt.score

        # Emit repair start event
        emit_event(
            run_id=pipeline.run_id,
            event_type="run.repair.started",
            payload={"iteration": iteration + 1, "prior_score": receipt.score, "verdict": receipt.verdict},
            session=session,
        )

        # 2. Build Failure Bundle
        violations = [c.title for c in receipt.constraints if c.result == "FAIL"]
        failing_proofs = [p.criterion_id for p in receipt.proofs if p.head != "PASS"]
        survivors = [s.op for s in receipt.mutation.survivors]

        bundle = FailureBundle(
            verdict=receipt.verdict,
            score=receipt.score,
            failing_proofs=failing_proofs,
            surviving_mutants=survivors,
            constraint_violations=violations,
            prior_score=last_score,
        )

        # 3. Propose and apply patch
        patch_res = patcher.propose_and_apply_patch(repo_path, bundle)
        if not patch_res.success:
            logger.warning("patch_generation_failed_or_rejected", reason=patch_res.rejection_reason)
            receipt.repair_history = repair_history
            receipt.iterations = iteration
            return receipt

        # Emit patch artifact event
        emit_event(
            run_id=pipeline.run_id,
            event_type="run.artifact",
            payload={"id": f"ar_patch_{iteration}", "kind": "diff", "url": f"/artifacts/ar_patch_{iteration}"},
            session=session,
        )

    return current_receipt or receipt
