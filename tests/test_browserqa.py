import pytest
from pathlib import Path

from receipt_api.verify.browserqa import (
    is_browser_qa_applicable,
    run_browser_qa,
)


def test_browser_qa_detection(tmp_path):
    # Pure library repo
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "math.py").write_text("def add(a, b): return a + b\n")
    assert not is_browser_qa_applicable(lib_dir)

    # Web repo with Jinja templates and FastAPI
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "templates").mkdir()
    (web_dir / "templates" / "index.html").write_text("<html><body>Cart</body></html>")
    (web_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    assert is_browser_qa_applicable(web_dir)


def test_browser_qa_execution(tmp_path):
    web_dir = tmp_path / "web_app"
    web_dir.mkdir()
    (web_dir / "templates").mkdir()
    (web_dir / "templates" / "index.html").write_text("<h1>TipJar Shop</h1>")
    (web_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")

    artifact_dir = tmp_path / "artifacts"

    # 1. Correct branch run
    results_correct = run_browser_qa(
        repo_path=web_dir,
        artifact_dir=artifact_dir,
        is_subtle_branch=False,
    )
    assert results_correct.applicable is True
    assert len(results_correct.checks) >= 3
    assert all(c.result == "PASS" for c in results_correct.checks)

    # Verify screenshot files exist
    created_pngs = list(artifact_dir.glob("*.png"))
    assert len(created_pngs) >= 3

    # 2. Subtle bug branch run
    results_subtle = run_browser_qa(
        repo_path=web_dir,
        artifact_dir=artifact_dir,
        is_subtle_branch=True,
    )
    assert results_subtle.applicable is True
    failed_checks = [c for c in results_subtle.checks if c.result == "FAIL"]
    assert len(failed_checks) > 0
    assert any("invoice" in c.name.lower() or "cents" in c.name.lower() for c in failed_checks)
