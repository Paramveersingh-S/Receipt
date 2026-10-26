import pytest
from bench.receipt_eval.tasks import get_benchmark_tasks
from bench.receipt_eval.evaluator import evaluate_receipt_bench
from bench.scar_eval.evaluator import evaluate_scar_bench
from bench.runner import run_all_benchmarks
from fastapi.testclient import TestClient
from receipt_api.main import app


def test_benchmark_tasks_stratification():
    tasks = get_benchmark_tasks()
    assert len(tasks) == 24

    flawed = [t for t in tasks if not t.is_correct]
    correct = [t for t in tasks if t.is_correct]

    assert len(flawed) == 12
    assert len(correct) == 12

    # Verify self-testing failure mode: 100% of candidate PRs author tests that pass in their branch
    assert all(t.pr_tests_pass is True for t in tasks)

    # Verify ground truth hidden tests pass ONLY on correct PRs
    assert all(t.hidden_tests_pass is True for t in correct)
    assert all(t.hidden_tests_pass is False for t in flawed)


def test_receipt_bench_evaluator():
    res = evaluate_receipt_bench()
    assert res["summary"]["total_tasks"] == 24
    assert len(res["comparisons"]) == 4

    systems = {c["system"]: c for c in res["comparisons"]}
    assert "Baseline A (PR tests only)" in systems
    assert "Baseline B (LLM-reviewer diff)" in systems
    assert "Receipt (Ablation: No Scar Tissue)" in systems
    assert "Receipt (Full System)" in systems

    # Defect detection must monotonically improve across methodologies
    det_a = systems["Baseline A (PR tests only)"]["detection_rate"]
    det_b = systems["Baseline B (LLM-reviewer diff)"]["detection_rate"]
    det_abl = systems["Receipt (Ablation: No Scar Tissue)"]["detection_rate"]
    det_full = systems["Receipt (Full System)"]["detection_rate"]

    assert det_a < det_b < det_abl <= det_full
    assert det_full >= 0.95
    assert systems["Receipt (Full System)"]["false_positive_rate"] <= 0.05
    assert systems["Receipt (Full System)"]["repair_success_rate"] >= 0.90


def test_scar_bench_evaluator():
    res = evaluate_scar_bench()
    assert res["planted_lessons_count"] == 7
    assert res["recovered_lessons_count"] == 7
    assert res["recall"] == 1.0
    assert res["precision"] >= 0.85
    assert res["retrieval_metrics"]["recall_at_3"] == 1.00
    assert res["false_positive_audit"]["noise_rate"] <= 0.10


def test_bench_api_endpoint():
    # Run benchmark to ensure files are fresh
    run_all_benchmarks()

    client = TestClient(app)
    res = client.get("/bench/results")
    assert res.status_code == 200
    data = res.json()

    assert data["summary"]["total_tasks"] == 24
    assert len(data["comparisons"]) == 4
    assert data["scar_eval"]["recall"] == 1.0
