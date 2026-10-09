"""Fetch only the first unique licenses from the requested test CSV.

This is adapted from fetch-first-ten.py. It persists one source manifest and
one HTML file per selected license so an interrupted run can resume without
touching later CSV rows.
"""
import argparse
import csv
import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--cache", default="test-batch-50")
parser.add_argument("--count", type=int, default=50)
args = parser.parse_args()

if args.count > 50:
    raise SystemExit("Safety limit: test batch fetch cannot exceed 50 licenses")

input_path = Path(args.input).resolve()
cache = ROOT / "exports" / args.cache
cache.mkdir(parents=True, exist_ok=True)
manifest_path = cache / "source-rows.json"

with input_path.open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    selected = []
    seen = set()
    for row in reader:
        license_number = (row.get("license_number") or "").strip()
        if not license_number or license_number in seen:
            continue
        seen.add(license_number)
        selected.append(row)
        if len(selected) >= args.count:
            break

if len(selected) < args.count:
    print(f"Input contains {len(selected)} unique licenses; processing all available unique licenses.")

check_date = datetime.now().astimezone().date().isoformat()
existing = {}
if manifest_path.exists():
    try:
        existing = {row["input"]["license_number"]: row for row in json.loads(manifest_path.read_text(encoding="utf-8-sig"))}
    except (ValueError, KeyError, TypeError):
        existing = {}

results = []
for index, row in enumerate(selected, start=1):
    license_number = row["license_number"].strip()
    prior = existing.get(license_number)
    html_path = cache / f"{license_number}.html"
    reusable = bool(
        prior
        and prior.get("check_date") == check_date
        and prior.get("error") == ""
        and html_path.exists()
    )
    if reusable:
        results.append(prior)
        print(index, row["name"], "Reused current cached page", flush=True)
        continue

    error = ""
    checked_at = datetime.now().astimezone().isoformat()
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                row["license_url"],
                headers={"User-Agent": "Mozilla/5.0 (compatible; CDI recruiting test batch)"},
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                document = response.read().decode("utf-8-sig", errors="replace")
            if not re.search(r"License #:\s*" + re.escape(license_number) + r"\s*<", document):
                raise ValueError("license identity mismatch or unavailable CDI record")
            html_path.write_text(document, encoding="utf-8")
            error = ""
            break
        except Exception as exc:  # retain the failure as review evidence
            error = str(exc)
            if attempt < 2:
                time.sleep(2)

    result = {
        "input": row,
        "check_date": check_date,
        "checked_at": checked_at,
        "error": error,
    }
    results.append(result)
    manifest_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(index, row["name"], "Fetched" if not error else f"REVIEW: {error}", flush=True)
    time.sleep(0.75)

manifest_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"input": str(input_path), "selected": len(results), "check_date": check_date, "errors": sum(bool(r["error"]) for r in results)}, indent=2))
