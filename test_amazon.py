"""
test_amazon.py — Automated end-to-end test for the Amazon scraper.

Usage:
    python test_amazon.py

What it does:
    1. Submits a scrape job for an Amazon product via the API
    2. Polls until the job completes (or fails) with a timeout
    3. Validates the result fields
    4. Downloads and saves the CSV export
    5. Prints a PASS/FAIL report
"""

import time
import requests
import sys

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8000"
POLL_INTERVAL = 5       # seconds between status checks
TIMEOUT = 120           # max seconds to wait for job to complete

TEST_CASES = [
    {
        "name": "Amazon Echo Dot (newest model)",
        "url": "https://www.amazon.com/dp/B09B8V1LZ3?th=1",
        "expect_title_contains": "Echo Dot",
        "expect_currency": "USD",
        "expect_price_range": (20.0, 200.0),  # sane $ range
    },
    # Add more test cases here for other ASINs
    # {
    #     "name": "Amazon Fire Stick",
    #     "url": "https://www.amazon.com/dp/B0BTJGNGSN",
    #     "expect_title_contains": "Fire TV",
    #     "expect_currency": "USD",
    #     "expect_price_range": (20.0, 80.0),
    # },
]
# ─────────────────────────────────────────────────────────────────────────────


def submit_job(url: str) -> int:
    resp = requests.post(f"{BASE_URL}/jobs/", json={"url": url})
    resp.raise_for_status()
    job_id = resp.json()["id"]
    print(f"  → Job submitted: ID {job_id}")
    return job_id


def poll_job(job_id: int, timeout: int, interval: int) -> dict:
    elapsed = 0
    while elapsed < timeout:
        resp = requests.get(f"{BASE_URL}/jobs/{job_id}")
        resp.raise_for_status()
        job = resp.json()
        status = job["status"]

        if status == "completed":
            return job
        elif status == "failed":
            return job
        else:
            print(f"  ⏳ Status: {status} ({elapsed}s elapsed)...")
            time.sleep(interval)
            elapsed += interval

    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def validate_result(job: dict, case: dict) -> list[str]:
    """Returns a list of failure messages. Empty = PASSED."""
    failures = []
    data = job.get("extracted_data") or {}

    if job["status"] != "completed":
        failures.append(f"Job status is '{job['status']}', expected 'completed'")
        failures.append(f"Error detail: {data.get('error', 'No error detail')}")
        return failures  # no point checking data fields

    # Title check
    title = data.get("title", "")
    if case["expect_title_contains"].lower() not in title.lower():
        failures.append(f"Title mismatch: expected to contain '{case['expect_title_contains']}', got: '{title}'")

    # Currency check
    currency = data.get("currency", "")
    if currency != case["expect_currency"]:
        failures.append(f"Currency mismatch: expected '{case['expect_currency']}', got '{currency}'")

    # Price check
    try:
        price = float(data.get("price", 0))
        lo, hi = case["expect_price_range"]
        if not (lo <= price <= hi):
            failures.append(f"Price out of expected range: ${price:.2f} not in ${lo}–${hi}")
    except (ValueError, TypeError):
        failures.append(f"Price is not a valid number: '{data.get('price')}'")

    # scrape_status check
    if data.get("status") != "Success":
        failures.append(f"Scrape status is '{data.get('status')}', expected 'Success'")

    return failures


def download_csv(job_id: int, filename: str):
    resp = requests.get(f"{BASE_URL}/jobs/{job_id}/export")
    resp.raise_for_status()
    with open(filename, "wb") as f:
        f.write(resp.content)
    print(f"  📥 CSV saved: {filename}")


# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Amazon Scraper — Automated Test Suite")
    print("=" * 60)

    all_passed = True

    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n[Test {i}] {case['name']}")
        print(f"  URL: {case['url']}")

        try:
            # 1. Submit
            job_id = submit_job(case["url"])

            # 2. Poll
            job = poll_job(job_id, timeout=TIMEOUT, interval=POLL_INTERVAL)
            data = job.get("extracted_data") or {}
            print(f"  📦 Result: {data}")

            # 3. Validate
            failures = validate_result(job, case)

            if failures:
                all_passed = False
                print(f"  ❌ FAILED")
                for f in failures:
                    print(f"     • {f}")
            else:
                print(f"  ✅ PASSED — Price: ${data.get('price')} {data.get('currency')}")

                # 4. Download CSV
                csv_file = f"test_result_job_{job_id}.csv"
                download_csv(job_id, csv_file)

        except Exception as e:
            all_passed = False
            print(f"  ❌ EXCEPTION: {e}")

    # 5. Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("  🎉 ALL TESTS PASSED")
    else:
        print("  ⚠️  SOME TESTS FAILED — check output above")
    print("=" * 60)
    sys.exit(0 if all_passed else 1)
