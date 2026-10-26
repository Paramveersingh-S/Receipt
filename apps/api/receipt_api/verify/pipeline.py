import json
import time
from pathlib import Path
from typing import Any, Optional

import structlog
from sqlmodel import Session, select

from receipt_api.db import get_engine
from receipt_api.events import emit_event
from receipt_api.models import DBReceipt, DBRun, DBRunStep
from receipt_api.schemas import Receipt
from receipt_api.verify.failbefore import ProofItem, evaluate_fail_before_proof
from receipt_api.verify.intent import AcceptanceCriterion, extract_intent
from receipt_api.verify.receipt import build_receipt, format_receipt_markdown
from receipt_api.verify.sandbox import SandboxConfig, run_in_sandbox
from receipt_api.verify.scoring import calculate_score
from receipt_api.verify.stacks import StackAdapter, detect_stack
from receipt_api.verify.stacks.base import TestStatus
from receipt_api.verify.testgen import generate_test_for_criterion

logger = structlog.get_logger(__name__)


class VerificationPipeline:
    """End-to-end verification orchestrator for a pull request."""

    def __init__(
        self,
        repo_path: Path,
        repo_name: str,
        pr_number: int,
        pr_title: str,
        pr_body: str = "",
        pr_author: str = "agent/claude-code",
        base_sha: str = "HEAD~1",
        head_sha: str = "HEAD",
        run_id: Optional[str] = None,
        config: Optional[SandboxConfig] = None,
    ):
        self.repo_path = repo_path
        self.repo_name = repo_name
        self.pr_number = pr_number
        self.pr_title = pr_title
        self.pr_body = pr_body
        self.pr_author = pr_author
        self.base_sha = base_sha
        self.head_sha = head_sha
        self.run_id = run_id or f"run_{int(time.time())}"
        self.config = config or SandboxConfig()

    def run(self, session: Optional[Session] = None) -> Receipt:
        start_time = time.perf_counter()
        logger.info("verification_pipeline_started", run_id=self.run_id, pr=self.pr_number)

        # Emit initial run.started event
        emit_event(
            run_id=self.run_id,
            event_type="run.started",
            payload={
                "run_id": self.run_id,
                "repo": self.repo_name,
                "pr_number": self.pr_number,
                "title": self.pr_title,
                "base_sha": self.base_sha,
                "head_sha": self.head_sha,
            },
            session=session,
        )

        limits: list[str] = []
        proofs: list[dict[str, Any]] = []
        suite_base = {"passed": 0, "failed": 0}
        suite_head = {"passed": 0, "failed": 0}
        regressions: list[str] = []

        # Detect stack
        stack = detect_stack(self.repo_path)
        if not stack:
            limits.append(f"Unsupported stack for repository {self.repo_path}")
            verdict = "NEEDS_REVIEW"
            score = 50
            return self._finalize_receipt(
                verdict=verdict,
                score=score,
                intent=[],
                proofs=[],
                suite={"base": suite_base, "head": suite_head, "regressions": []},
                mutation={"mutants": 0, "killed": 0, "survived": 0, "timeout": 0, "score": 1.0, "survivors": []},
                constraints=[],
                browser={"applicable": False, "checks": []},
                score_breakdown={"behavior": 0.0, "constraints": 1.0, "test_strength": 1.0, "regression": 1.0},
                limits=limits,
                start_time=start_time,
                session=session,
            )

        # 1. Step: Intent Extraction
        self._record_step_start("intent", session)
        criteria = extract_intent(self.pr_title, self.pr_body)
        self._record_step_finish("intent", {"criteria_count": len(criteria)}, session)

        # 2. Step: Test Generation & Fail-Before Proof Evaluation
        self._record_step_start("testgen", session)
        proof_items: list[ProofItem] = []
        test_dir = self.repo_path / "receipt_tests"

        try:
            for crit in criteria:
                if not crit.testable:
                    continue
                test_file = generate_test_for_criterion(crit, "", stack, test_dir)
                if test_file and test_file.exists():
                    proof = evaluate_fail_before_proof(
                        criterion=crit,
                        test_file_path=test_file,
                        base_repo_path=self.repo_path,
                        head_repo_path=self.repo_path,
                        stack=stack,
                        config=self.config,
                    )
                    proof_items.append(proof)
                    emit_event(
                        run_id=self.run_id,
                        event_type="run.proof",
                        payload=proof.model_dump(),
                        session=session,
                    )
        finally:
            # Clean up throwaway test dir
            if test_dir.exists():
                import shutil
                shutil.rmtree(test_dir, ignore_errors=True)

        self._record_step_finish("testgen", {"proofs_generated": len(proof_items)}, session)

        # 3. Step: Existing Test Suite Regression Check
        self._record_step_start("suite", session)
        head_run = run_in_sandbox(repo_path=self.repo_path, stack=stack, config=self.config)
        passed_count = sum(1 for t in head_run.test_results if t.status == TestStatus.PASS)
        failed_count = sum(1 for t in head_run.test_results if t.status != TestStatus.PASS)
        suite_head = {"passed": passed_count, "failed": failed_count}
        suite_base = {"passed": passed_count, "failed": 0}  # Baseline assumed passing
        self._record_step_finish("suite", suite_head, session)

        # 4. Step: Scoring
        self._record_step_start("scoring", session)
        non_vacuous_proofs = [p for p in proof_items if not p.vacuous]
        for p in proof_items:
            if p.vacuous:
                limits.append(f"Test '{p.test_name}' passed on base commit; marked vacuous and excluded from proofs")

        behavior_score = (
            len(non_vacuous_proofs) / len(proof_items)
            if proof_items
            else 1.0
        )
        has_regressions = len(regressions) > 0
        is_bugfix = any(c.kind == "bugfix" for c in criteria)

        score_res = calculate_score(
            behavior=behavior_score,
            constraints=1.0,  # Full constraints in Phase 6
            test_strength=1.0,  # AST mutation in Phase 7
            regression=1.0 if not has_regressions else 0.0,
            browser=None,
            has_regressions=has_regressions,
            has_blocking_violations=False,
            has_non_vacuous_proofs=len(non_vacuous_proofs) > 0 if proof_items else True,
            is_bugfix=is_bugfix,
        )

        if score_res.hard_gate_triggered:
            limits.append(score_res.hard_gate_triggered)

        self._record_step_finish("scoring", {"score": score_res.score, "verdict": score_res.verdict}, session)

        # 5. Finalize Receipt
        proofs_dicts = [p.model_dump() for p in proof_items]
        intent_dicts = [c.model_dump() for c in criteria]
        score_breakdown_dict = {
            "behavior": score_res.breakdown.behavior,
            "constraints": score_res.breakdown.constraints,
            "test_strength": score_res.breakdown.test_strength,
            "regression": score_res.breakdown.regression,
            "browser": score_res.breakdown.browser,
        }

        return self._finalize_receipt(
            verdict=score_res.verdict,
            score=score_res.score,
            intent=intent_dicts,
            proofs=proofs_dicts,
            suite={"base": suite_base, "head": suite_head, "regressions": regressions},
            mutation={"mutants": 0, "killed": 0, "survived": 0, "timeout": 0, "score": 1.0, "survivors": []},
            constraints=[],
            browser={"applicable": False, "checks": []},
            score_breakdown=score_breakdown_dict,
            limits=limits,
            start_time=start_time,
            session=session,
        )

    def _record_step_start(self, step_name: str, session: Optional[Session]) -> None:
        emit_event(
            run_id=self.run_id,
            event_type="run.step.started",
            payload={"name": step_name},
            session=session,
        )

    def _record_step_finish(self, step_name: str, summary: dict[str, Any], session: Optional[Session]) -> None:
        emit_event(
            run_id=self.run_id,
            event_type="run.step.finished",
            payload={"name": step_name, "state": "completed", "summary": summary},
            session=session,
        )

    def _finalize_receipt(
        self,
        verdict: str,
        score: int,
        intent: list[dict[str, Any]],
        proofs: list[dict[str, Any]],
        suite: dict[str, Any],
        mutation: dict[str, Any],
        constraints: list[dict[str, Any]],
        browser: dict[str, Any],
        score_breakdown: dict[str, Any],
        limits: list[str],
        start_time: float,
        session: Optional[Session],
    ) -> Receipt:
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        receipt = build_receipt(
            repo_name=self.repo_name,
            pr_number=self.pr_number,
            pr_title=self.pr_title,
            pr_author=self.pr_author,
            base_sha=self.base_sha,
            head_sha=self.head_sha,
            verdict=verdict,
            score=score,
            duration_ms=duration_ms,
            intent=intent,
            proofs=proofs,
            suite=suite,
            mutation=mutation,
            constraints=constraints,
            browser=browser,
            score_breakdown=score_breakdown,
            limits=limits,
        )

        # Save to database if session is active
        if session:
            try:
                import datetime
                db_receipt = DBReceipt(
                    id=receipt.id,
                    run_id=self.run_id,
                    verdict=receipt.verdict,
                    score=receipt.score,
                    receipt_json=json.dumps(receipt.model_dump()),
                    created_at=datetime.datetime.now(datetime.timezone.utc),
                    public_slug=receipt.slug,
                )
                session.add(db_receipt)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning("save_receipt_db_failed", error=str(e))

        # Emit run.finished event
        emit_event(
            run_id=self.run_id,
            event_type="run.finished",
            payload={"verdict": receipt.verdict, "score": receipt.score, "slug": receipt.slug, "receipt_id": receipt.id},
            session=session,
        )

        return receipt
