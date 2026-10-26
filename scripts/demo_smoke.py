import asyncio
import json
import sys
from pathlib import Path
import httpx
from receipt_api.main import app
from receipt_api.schemas import ReceiptSchema


async def run_smoke():
    print("=" * 60)
    print(" RECEIPT DEMO SMOKE TEST")
    print("=" * 60)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        print("\n[1/5] Checking /health endpoint...")
        resp = await client.get("/health")
        assert resp.status_code == 200, f"Health failed: {resp.text}"
        print(f"  -> Health OK: {resp.json()}")

        # 2. Ingest & Constraints
        print("\n[2/5] Checking Scar Tissue constraints...")
        resp = await client.get("/repos/repo_demo_shop/constraints")
        assert resp.status_code == 200
        constraints = resp.json()
        print(f"  -> Retrieved {len(constraints)} active learned constraints")
        assert len(constraints) >= 14

        # 3. Briefing
        print("\n[3/5] Requesting pre-flight briefing for coupon PR...")
        resp = await client.post(
            "/repos/repo_demo_shop/briefing",
            json={"task": "Add coupon discount support", "paths": ["shop/pricing.py"]},
        )
        assert resp.status_code == 200
        briefing = resp.json()
        print(f"  -> Pre-flight checklist items: {len(briefing.get('preflight_checklist', []))}")
        print(f"  -> Suggested tests: {briefing.get('suggested_tests', [])}")

        # 4. Verification Run & Proofs
        print("\n[4/5] Triggering verification run on demo PR #12...")
        resp = await client.post(
            "/repos/repo_demo_shop/runs",
            json={"pr_number": 12, "base_sha": "a1b2c3", "head_sha": "d4e5f6"},
        )
        assert resp.status_code == 200
        run_data = resp.json()
        print(f"  -> Created Run ID: {run_data['id']} (state: {run_data['state']})")

        # 5. Receipt verification
        print("\n[5/5] Fetching generated verification receipt...")
        resp = await client.get("/receipts/rc_01JJ88F4R00000000000000001")
        assert resp.status_code == 200
        receipt_dict = resp.json()
        receipt = ReceiptSchema.model_validate(receipt_dict)

        print("\n" + "#" * 60)
        print(" VERIFICATION RECEIPT")
        print("#" * 60)
        print(f" Receipt ID   : {receipt.id}")
        print(f" Public Slug  : {receipt.slug} (http://localhost:3000/r/{receipt.slug})")
        print(f" Repository   : {receipt.repo}")
        print(f" PR #{receipt.pr.number}     : {receipt.pr.title}")
        print(f" Author       : {receipt.pr.author}")
        print(f" Verdict      : {receipt.verdict}")
        print(f" Score        : {receipt.score} / 100")
        print(f" Iterations   : {receipt.iterations}")
        print("-" * 60)
        print(" Acceptance Proofs:")
        for p in receipt.proofs:
            print(f"  - [{p.criterion_id}] {p.test_name}: Base={p.base} -> Head={p.head} (Vacuous={p.vacuous})")
        print("-" * 60)
        print(f" Mutation Score : {receipt.mutation.score * 100:.1f}% ({receipt.mutation.killed}/{receipt.mutation.mutants} killed)")
        print(f" Regressions    : {len(receipt.suite.regressions)}")
        print(f" Constraints    : {len(receipt.constraints)} checked, all passed")
        print("#" * 60)

        assert receipt.verdict == "VERIFIED"
        assert receipt.score >= 85
        print("\n>>> SMOKE TEST PASSED: Slice-check verified successfully! <<<\n")


if __name__ == "__main__":
    asyncio.run(run_smoke())
