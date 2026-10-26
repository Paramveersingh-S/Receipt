import pytest
from pathlib import Path

from receipt_api.repair.external import ExternalAgentRepair
from receipt_api.repair.loop import run_repair_loop
from receipt_api.repair.patcher import (
    FailureBundle,
    PatchLLMRepair,
    check_patch_guardrails,
)


def test_patch_guardrails():
    # 1. Rejects test-weakening diff
    bad_diff = """--- a/tests/test_pricing.py
+++ b/tests/test_pricing.py
@@ -10,2 +10,3 @@
+@pytest.mark.skip
 def test_coupon_rounding():
"""
    valid, reason = check_patch_guardrails(bad_diff)
    assert not valid
    assert "weaken/skip tests" in reason

    # 2. Rejects assert True weakening
    assert_true_diff = """--- a/tests/test_checkout.py
+++ b/tests/test_checkout.py
@@ -15,2 +15,2 @@
-    assert invoice.total == 800
+    assert True
"""
    valid2, reason2 = check_patch_guardrails(assert_true_diff)
    assert not valid2
    assert "assert True" in reason2

    # 3. Accepts clean patch
    good_diff = """--- a/shop/pricing.py
+++ b/shop/pricing.py
@@ -40,2 +40,2 @@
-    return total * 0.15
+    return (total * 15 + 50) // 100
"""
    valid3, reason3 = check_patch_guardrails(good_diff, allowed_files=["shop/pricing.py"])
    assert valid3
    assert reason3 is None


def test_repair_loop_subtle_bug_recovers_to_verified(tmp_path):
    repo_dir = tmp_path / "shop_repo"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text('[project]\nname = "demo-shop"\nversion = "0.1.0"\n', encoding="utf-8")

    shop_dir = repo_dir / "shop"
    shop_dir.mkdir()

    # Initial subtle bug code
    pricing_file = shop_dir / "pricing.py"
    pricing_file.write_text(
        "def compute_discount(price_cents, discount_pct):\n"
        "    return price_cents * 0.15\n",
        encoding="utf-8",
    )

    checkout_file = shop_dir / "checkout.py"
    checkout_file.write_text(
        "def charge_customer(order_id, amount):\n"
        "    return gateway.charge(order_id=order_id, amount=amount)\n",
        encoding="utf-8",
    )

    test_file = repo_dir / "test_shop.py"
    test_file.write_text(
        "class MockGateway:\n"
        "    def charge(self, order_id, amount, idempotency_key=None):\n"
        "        return {'order_id': order_id, 'amount': amount, 'key': idempotency_key}\n"
        "import shop.checkout\n"
        "shop.checkout.gateway = MockGateway()\n"
        "from shop.pricing import compute_discount\n"
        "from shop.checkout import charge_customer\n"
        "def test_pricing():\n"
        "    assert compute_discount(100, 15) == 15\n"
        "def test_checkout():\n"
        "    res = charge_customer('ord_1', 100)\n"
        "    assert res['amount'] == 100\n",
        encoding="utf-8",
    )

    # Run repair loop
    final_receipt = run_repair_loop(
        repo_path=repo_dir,
        repo_name="demo/shop",
        pr_number=12,
        pr_title="Add coupon support",
        pr_body="Adds discount calculation with percentage discount",
        max_iterations=3,
    )

    # Must have recovered through repair iterations
    assert len(final_receipt.repair_history) >= 1
    assert final_receipt.repair_history[0].iteration == 1
    assert final_receipt.repair_history[0].verdict in ("NEEDS_REVIEW", "REJECTED")

    # Final receipt must be VERIFIED with clean invariants
    assert final_receipt.verdict == "VERIFIED"
    assert final_receipt.score >= 85


def test_external_repair_markdown():
    bundle = FailureBundle(
        verdict="REJECTED",
        score=52,
        failing_proofs=["ac1"],
        surviving_mutants=["ROUND_TO_INT on line 42"],
        constraint_violations=["Money is integer cents, never float"],
    )
    comment = ExternalAgentRepair.format_failure_comment(
        bundle=bundle,
        repo_full_name="acme/receipt-demo-shop",
        pr_number=12,
    )
    assert "Receipt Verification Failed" in comment
    assert "Money is integer cents, never float" in comment
    assert "ROUND_TO_INT" in comment
