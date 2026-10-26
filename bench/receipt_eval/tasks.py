from dataclasses import dataclass
from typing import List, Optional, Literal

FlawKind = Literal[
    "float_cents",
    "bare_except",
    "missing_idempotency",
    "n_plus_one",
    "missing_auth",
    "pii_logging",
    "unreversible_migration",
]


@dataclass
class BenchmarkTask:
    id: str
    repo: str
    title: str
    is_correct: bool
    subtle_flaw: Optional[FlawKind]
    pr_diff: str
    pr_tests_pass: bool  # 100% of benchmark PRs pass their own authored tests
    hidden_tests_pass: bool  # Ground truth: held-out tests pass ONLY if code is truly correct


def get_benchmark_tasks() -> List[BenchmarkTask]:
    """Return 24 stratified benchmark PR tasks (12 correct, 12 subtly flawed)."""
    tasks: List[BenchmarkTask] = []

    # 1. demo-shop: Coupon calculation (Flawed: float cents)
    tasks.append(
        BenchmarkTask(
            id="task_001_demo_shop_coupon_subtle",
            repo="receipt-demo-shop",
            title="Implement 15% discount coupon computation",
            is_correct=False,
            subtle_flaw="float_cents",
            pr_diff="""--- a/shop/pricing.py
+++ b/shop/pricing.py
@@ -35,3 +35,3 @@
 def compute_coupon_discount(price_cents: int, pct: int) -> int:
-    return 0
+    return int(price_cents * 0.15)
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 2. demo-shop: Coupon calculation (Correct: integer cents rounding)
    tasks.append(
        BenchmarkTask(
            id="task_002_demo_shop_coupon_correct",
            repo="receipt-demo-shop",
            title="Implement 15% discount coupon computation with integer rounding",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/shop/pricing.py
+++ b/shop/pricing.py
@@ -35,3 +35,3 @@
 def compute_coupon_discount(price_cents: int, pct: int) -> int:
-    return 0
+    return (price_cents * pct + 50) // 100
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 3. demo-shop: Checkout payment (Flawed: missing idempotency key)
    tasks.append(
        BenchmarkTask(
            id="task_003_demo_shop_payment_no_idempotency",
            repo="receipt-demo-shop",
            title="Add automated Stripe card charge in checkout flow",
            is_correct=False,
            subtle_flaw="missing_idempotency",
            pr_diff="""--- a/shop/checkout.py
+++ b/shop/checkout.py
@@ -80,3 +80,3 @@
 def process_checkout(cart_id: str, amount_cents: int):
-    pass
+    payment_client.charge(amount=amount_cents)
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 4. demo-shop: Checkout payment (Correct: with idempotency key)
    tasks.append(
        BenchmarkTask(
            id="task_004_demo_shop_payment_idempotent",
            repo="receipt-demo-shop",
            title="Add automated Stripe card charge with deterministic idempotency key",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/shop/checkout.py
+++ b/shop/checkout.py
@@ -80,3 +80,3 @@
 def process_checkout(cart_id: str, amount_cents: int, idempotency_key: str):
-    pass
+    payment_client.charge(amount=amount_cents, idempotency_key=idempotency_key)
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 5. demo-shop: Order discount fallback (Flawed: bare exception)
    tasks.append(
        BenchmarkTask(
            id="task_005_demo_shop_bare_except",
            repo="receipt-demo-shop",
            title="Safely catch discount lookup errors with default zero",
            is_correct=False,
            subtle_flaw="bare_except",
            pr_diff="""--- a/shop/discounts.py
+++ b/shop/discounts.py
@@ -20,3 +20,4 @@
 def get_discount_safe(code: str) -> int:
-    return 0
+    try: return lookup_remote(code)
+    except: return 0
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 6. demo-shop: Order discount fallback (Correct: explicit exception)
    tasks.append(
        BenchmarkTask(
            id="task_006_demo_shop_explicit_except",
            repo="receipt-demo-shop",
            title="Safely catch discount lookup errors with specific CouponNotFoundError",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/shop/discounts.py
+++ b/shop/discounts.py
@@ -20,3 +20,4 @@
 def get_discount_safe(code: str) -> int:
-    return 0
+    try: return lookup_remote(code)
+    except CouponNotFoundError: return 0
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 7. demo-shop: Admin export endpoint (Flawed: missing auth dependency)
    tasks.append(
        BenchmarkTask(
            id="task_007_demo_shop_admin_no_auth",
            repo="receipt-demo-shop",
            title="Add fast admin CSV export endpoint for order history",
            is_correct=False,
            subtle_flaw="missing_auth",
            pr_diff="""--- a/shop/api/admin.py
+++ b/shop/api/admin.py
@@ -12,2 +12,3 @@
+@router.get("/admin/export/orders")
+def export_orders(): return generate_csv()
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 8. demo-shop: Admin export endpoint (Correct: with admin auth dependency)
    tasks.append(
        BenchmarkTask(
            id="task_008_demo_shop_admin_with_auth",
            repo="receipt-demo-shop",
            title="Add fast admin CSV export endpoint with require_admin dependency",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/shop/api/admin.py
+++ b/shop/api/admin.py
@@ -12,2 +12,3 @@
+@router.get("/admin/export/orders", dependencies=[Depends(require_admin)])
+def export_orders(): return generate_csv()
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 9. tiny-ledger: Batch transaction processing (Flawed: N+1 query loop)
    tasks.append(
        BenchmarkTask(
            id="task_009_tiny_ledger_n_plus_one",
            repo="tiny-ledger",
            title="Fetch account balances for transaction batch",
            is_correct=False,
            subtle_flaw="n_plus_one",
            pr_diff="""--- a/ledger/batch.py
+++ b/ledger/batch.py
@@ -40,3 +40,4 @@
 def compute_batch_balances(account_ids):
-    return []
+    for aid in account_ids:
+        db.session.execute("SELECT balance FROM accounts WHERE id = :id", {"id": aid})
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 10. tiny-ledger: Batch transaction processing (Correct: bulk query IN)
    tasks.append(
        BenchmarkTask(
            id="task_010_tiny_ledger_bulk_query",
            repo="tiny-ledger",
            title="Fetch account balances using bulk WHERE id IN query",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/ledger/batch.py
+++ b/ledger/batch.py
@@ -40,3 +40,3 @@
 def compute_batch_balances(account_ids):
-    return []
+    return db.session.execute("SELECT id, balance FROM accounts WHERE id IN :ids", {"ids": account_ids}).all()
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 11. tiny-ledger: Audit logging (Flawed: PII card logging)
    tasks.append(
        BenchmarkTask(
            id="task_011_tiny_ledger_pii_log",
            repo="tiny-ledger",
            title="Log audit trail for customer payment methods",
            is_correct=False,
            subtle_flaw="pii_logging",
            pr_diff="""--- a/ledger/audit.py
+++ b/ledger/audit.py
@@ -15,2 +15,3 @@
 def log_payment_event(card_number, amount):
+    logger.info("payment_processed", card_number=card_number, amount=amount)
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 12. tiny-ledger: Audit logging (Correct: masked token logging)
    tasks.append(
        BenchmarkTask(
            id="task_012_tiny_ledger_masked_log",
            repo="tiny-ledger",
            title="Log audit trail using masked payment token",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/ledger/audit.py
+++ b/ledger/audit.py
@@ -15,2 +15,3 @@
 def log_payment_event(card_number, amount):
+    logger.info("payment_processed", card_last4=card_number[-4:], amount=amount)
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 13. tiny-ledger: Database migration (Flawed: irreversible column drop)
    tasks.append(
        BenchmarkTask(
            id="task_013_tiny_ledger_irreversible_migration",
            repo="tiny-ledger",
            title="Drop deprecated legacy_balance column",
            is_correct=False,
            subtle_flaw="unreversible_migration",
            pr_diff="""--- a/alembic/versions/004_drop_col.py
+++ b/alembic/versions/004_drop_col.py
@@ -15,4 +15,4 @@
 def upgrade():
-    pass
+    op.drop_column('accounts', 'legacy_balance')
 def downgrade():
+    pass
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 14. tiny-ledger: Database migration (Correct: reversible migration)
    tasks.append(
        BenchmarkTask(
            id="task_014_tiny_ledger_reversible_migration",
            repo="tiny-ledger",
            title="Drop deprecated column with rollback restoration definition",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/alembic/versions/004_drop_col.py
+++ b/alembic/versions/004_drop_col.py
@@ -15,4 +15,4 @@
 def upgrade():
-    pass
+    op.drop_column('accounts', 'legacy_balance')
 def downgrade():
+    op.add_column('accounts', sa.Column('legacy_balance', sa.BigInteger(), nullable=True))
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 15. mini-url-service: Link expiration billing (Flawed: float math)
    tasks.append(
        BenchmarkTask(
            id="task_015_mini_url_prorate_float",
            repo="mini-url-service",
            title="Prorate premium custom slug reservation price",
            is_correct=False,
            subtle_flaw="float_cents",
            pr_diff="""--- a/shortener/billing.py
+++ b/shortener/billing.py
@@ -18,2 +18,3 @@
 def prorate_slug_price(base_cents, days):
+    return base_cents * (days / 30.0)
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 16. mini-url-service: Link expiration billing (Correct: integer math)
    tasks.append(
        BenchmarkTask(
            id="task_016_mini_url_prorate_int",
            repo="mini-url-service",
            title="Prorate premium custom slug reservation price with integer division",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/shortener/billing.py
+++ b/shortener/billing.py
@@ -18,2 +18,3 @@
 def prorate_slug_price(base_cents, days):
+    return (base_cents * days + 15) // 30
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 17. mini-url-service: Slug generation fallback (Flawed: bare exception)
    tasks.append(
        BenchmarkTask(
            id="task_017_mini_url_bare_except",
            repo="mini-url-service",
            title="Catch collision in slug generation loop",
            is_correct=False,
            subtle_flaw="bare_except",
            pr_diff="""--- a/shortener/slug.py
+++ b/shortener/slug.py
@@ -25,3 +25,4 @@
 def generate_unique_slug():
-    return 'default'
+    try: return create_random_slug()
+    except: return 'fallback'
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 18. mini-url-service: Slug generation fallback (Correct: IntegrityError)
    tasks.append(
        BenchmarkTask(
            id="task_018_mini_url_integrity_except",
            repo="mini-url-service",
            title="Catch slug collision with specific DB IntegrityError",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/shortener/slug.py
+++ b/shortener/slug.py
@@ -25,3 +25,4 @@
 def generate_unique_slug():
-    return 'default'
+    try: return create_random_slug()
+    except IntegrityError: return 'fallback'
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 19. mini-url-service: Webhook dispatch (Flawed: missing idempotency key)
    tasks.append(
        BenchmarkTask(
            id="task_019_mini_url_webhook_no_idempotency",
            repo="mini-url-service",
            title="Post click analytics webhook to subscriber endpoint",
            is_correct=False,
            subtle_flaw="missing_idempotency",
            pr_diff="""--- a/shortener/webhooks.py
+++ b/shortener/webhooks.py
@@ -30,2 +30,3 @@
 def dispatch_click_webhook(url, click_event):
+    httpx.post(url, json=click_event)
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 20. mini-url-service: Webhook dispatch (Correct: idempotency header)
    tasks.append(
        BenchmarkTask(
            id="task_020_mini_url_webhook_idempotency",
            repo="mini-url-service",
            title="Post click analytics webhook with Idempotency-Key header",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/shortener/webhooks.py
+++ b/shortener/webhooks.py
@@ -30,2 +30,3 @@
 def dispatch_click_webhook(url, click_event, event_id):
+    httpx.post(url, json=click_event, headers={"Idempotency-Key": event_id})
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 21. mini-url-service: Analytics aggregation (Flawed: N+1 query loop)
    tasks.append(
        BenchmarkTask(
            id="task_021_mini_url_n_plus_one",
            repo="mini-url-service",
            title="Summarize click counts across user domain URLs",
            is_correct=False,
            subtle_flaw="n_plus_one",
            pr_diff="""--- a/shortener/analytics.py
+++ b/shortener/analytics.py
@@ -15,3 +15,4 @@
 def aggregate_domain_clicks(slug_list):
-    return 0
+    for s in slug_list:
+        db.execute("SELECT count(*) FROM clicks WHERE slug = :s", {"s": s})
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 22. mini-url-service: Analytics aggregation (Correct: GROUP BY bulk query)
    tasks.append(
        BenchmarkTask(
            id="task_022_mini_url_group_by",
            repo="mini-url-service",
            title="Summarize click counts using single SQL GROUP BY query",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/shortener/analytics.py
+++ b/shortener/analytics.py
@@ -15,3 +15,3 @@
 def aggregate_domain_clicks(slug_list):
-    return 0
+    return db.execute("SELECT slug, count(*) FROM clicks WHERE slug IN :slugs GROUP BY slug", {"slugs": slug_list}).all()
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    # 23. mini-url-service: Telemetry logging (Flawed: PII secret logging)
    tasks.append(
        BenchmarkTask(
            id="task_023_mini_url_pii_logging",
            repo="mini-url-service",
            title="Log user API token usage in telemetry tracer",
            is_correct=False,
            subtle_flaw="pii_logging",
            pr_diff="""--- a/shortener/telemetry.py
+++ b/shortener/telemetry.py
@@ -10,2 +10,3 @@
 def trace_request(secret_key, path):
+    logger.info("api_access", secret_key=secret_key, path=path)
""",
            pr_tests_pass=True,
            hidden_tests_pass=False,
        )
    )

    # 24. mini-url-service: Telemetry logging (Correct: hashed key logging)
    tasks.append(
        BenchmarkTask(
            id="task_024_mini_url_hash_logging",
            repo="mini-url-service",
            title="Log user API token usage using SHA256 key fingerprint",
            is_correct=True,
            subtle_flaw=None,
            pr_diff="""--- a/shortener/telemetry.py
+++ b/shortener/telemetry.py
@@ -10,2 +10,3 @@
 def trace_request(secret_key, path):
+    logger.info("api_access", key_hash=hashlib.sha256(secret_key.encode()).hexdigest()[:8], path=path)
""",
            pr_tests_pass=True,
            hidden_tests_pass=True,
        )
    )

    return tasks
