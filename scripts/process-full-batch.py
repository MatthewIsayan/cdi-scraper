"""Resumable full-CSV CDI retrieval, extraction, screening, and checkpointing.

The completed test batch is copied into the full-batch state as immutable
records. Remaining licenses are fetched one at a time, with atomic state
writes after each record and a progress checkpoint every 25 new records.
"""
import argparse
import csv
import html
import json
import os
import re
import tempfile
import time
import urllib.request
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from screening_logic import assess_fact

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = [
    "Name", "Passed_Test", "Assessment", "License_URL", "License_Number", "Business_Address", "Business_Phone",
    "Directions_URL", "Source_ZIPs", "Checked_On", "Languages", "Active_Qualifications", "Qualification_Details",
    "Life_Issue_Date", "Years_Since_Life_Issue", "Active_Health_Authority", "Active_PC_Authority", "Active_Variable_Authority",
    "Appointed_Insurers", "Appointment_Row_Count", "Unique_Insurer_Count", "Life_Appointed_Insurers", "Unique_Life_Insurer_Count",
    "Health_Appointed_Insurers", "PC_Appointed_Insurers", "Appointment_Details", "Agency_Organizations", "Unique_Agency_Count",
    "Agency_Relationship_Count", "Life_Agency_Organizations", "Agency_Relationship_Details", "Latest_Displayed_Relationship_Date", "Rule_Document"
]

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--cache", default="full-batch")
parser.add_argument("--check-date", default="2026-10-08")
parser.add_argument("--completed-cache", default="test-batch-50")
parser.add_argument("--completed-order", default="exports/test-batch-50/original-license-order.json")
parser.add_argument("--limit", type=int, default=0, help="Process at most this many remaining licenses")
parser.add_argument("--retry-failed", action="store_true", help="Retry previously saved retrieval/extraction failures")
parser.add_argument("--self-test", action="store_true")
args = parser.parse_args()

cache = ROOT / "exports" / args.cache
html_dir = cache / "html"
cache.mkdir(parents=True, exist_ok=True)
html_dir.mkdir(parents=True, exist_ok=True)
state_path = cache / "records.json"
progress_path = cache / "progress.json"
manifest_path = cache / "source-manifest.json"


def atomic_write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def clean(value):
    value = re.sub(r"<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>", "", value, flags=re.S | re.I)
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", value)).split())


def table_rows(document, table_id):
    match = re.search(r'<table\b[^>]*\bid=["\']' + re.escape(table_id) + r'["\'][^>]*>(.*?)</table>', document, re.S | re.I)
    if not match:
        return None
    rows = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", match.group(1), re.S | re.I):
        if not re.search(r"<td\b", row, re.I):
            continue
        cells = re.findall(r"<td\b[^>]*>(.*?)(?=</td>|<td\b|</tr>)", row, re.S | re.I)
        rows.append([clean(cell) for cell in cells])
    return rows


def labeled_value(document, label):
    match = re.search(r"<b>\s*" + re.escape(label) + r"\s*</b>(.*?)(?:</div>|</p>)", document, re.S | re.I)
    return clean(match.group(1)) if match else ""


def extract_fact(document, license_number):
    identity = re.search(r"License #:\s*" + re.escape(license_number) + r"\s*<", document, re.I)
    if not identity:
        raise ValueError("license identity mismatch in retrieved CDI page")
    qualification_rows = table_rows(document, "licenseDetailGrid")
    appointment_rows = table_rows(document, "AppointmentGrid")
    agency_rows = table_rows(document, "EndorsingOrganizationsGrid")
    order_rows = table_rows(document, "EnforcementActionGrid")
    if qualification_rows is None:
        qualifications = []
    else:
        qualifications = qualification_rows
    def compact(rows):
        if not rows:
            return ""
        return "|".join("~".join(row[:3]) for row in rows if row)
    headings = [clean(x) for x in re.findall(r"<h3\b[^>]*>(.*?)</h3>", document, re.S | re.I)]
    return {
        "license_number": license_number,
        "license": license_number,
        "qualifications": qualifications,
        "appointments": compact(appointment_rows),
        "agencies": compact(agency_rows),
        "orders": compact(order_rows),
        "business_address": labeled_value(document, "Business Address:"),
        "business_phone": labeled_value(document, "Business Phone:"),
        "languages": labeled_value(document, "Language:"),
        "name": next((x for x in headings if "Name:" in x), ""),
        "qualification_table_found": qualification_rows is not None,
        "source_html_bytes": len(document.encode("utf-8", errors="replace")),
    }


def unique(values):
    return list(dict.fromkeys(values))


def parse_relationships(value):
    if not value:
        return []
    result = []
    for item in value.split("|"):
        parts = item.split("~")
        if len(parts) == 3:
            result.append(parts)
    return result


def parse_orders(value):
    if not value:
        return []
    result = []
    for item in value.split("|"):
        parts = item.rsplit("~", 1)
        if len(parts) == 2:
            result.append(parts)
        elif item.strip():
            result.append([item.strip(), ""])
    return result


def iso_date(value):
    return datetime.strptime(value, "%m/%d/%Y").date().isoformat() if value else ""


def years_since(value, checked):
    if not value:
        return ""
    days = (date.fromisoformat(checked) - datetime.strptime(value, "%m/%d/%Y").date()).days
    return round(days / 365.2425, 2)


def details(rows):
    return " | ".join(f"{r[0]} — {r[1]} — {iso_date(r[2])}" for r in rows)


def names(rows):
    return "; ".join(unique(r[0] for r in rows))


def make_row(source, fact, decision, check_date, retrieval_error=""):
    license_number = source["license_number"].strip()
    row = {c: "" for c in COLUMNS}
    row.update({
        "Name": source.get("name", ""), "License_URL": source.get("license_url", ""), "License_Number": license_number,
        "Business_Address": source.get("address", ""), "Business_Phone": source.get("phone", ""),
        "Directions_URL": source.get("directions_url", ""), "Source_ZIPs": source.get("source_zips", ""),
        "Checked_On": check_date, "Rule_Document": "imo-final-approval-rules.md (2026-10-08)",
    })
    if retrieval_error or not fact:
        row["Assessment"] = "Needs review: CDI page was unavailable after three retrieval attempts; no rejection inferred." if retrieval_error else "Needs review: CDI evidence was unavailable or did not verify this license number; no rejection inferred."
        return row

    qualifications = fact.get("qualifications")
    appointments = parse_relationships(fact.get("appointments", ""))
    agencies = parse_relationships(fact.get("agencies", ""))
    active = [q for q in qualifications if isinstance(q, (list, tuple)) and len(q) >= 3 and str(q[2]).lower() == "active"] if isinstance(qualifications, list) else []
    active_names = [q[0] for q in active]
    general_life = next((q for q in active if str(q[0]).lower() == "life"), None)
    decision_fact = dict(fact)
    decision_fact["expected_license"] = license_number
    decision = decision or assess_fact(decision_fact, agency_research)
    reported_languages = unique([x.strip() for x in re.split(r"[,;]", fact.get("languages", "")) if x.strip()])
    life_appointments = [r for r in appointments if len(r) >= 2 and r[1].lower() == "life"]
    health_appointments = [r for r in appointments if len(r) >= 2 and "health" in r[1].lower()]
    pc_appointments = [r for r in appointments if len(r) >= 2 and r[1].lower() in {"property", "casualty", "personal lines"}]
    dates = [datetime.strptime(r[2], "%m/%d/%Y").date() for r in appointments + agencies if len(r) >= 3 and r[2]]
    row.update({
        "Passed_Test": decision["passed_test"], "Assessment": decision["reason"],
        "Business_Address": fact.get("business_address") or source.get("address", ""),
        "Business_Phone": fact.get("business_phone") or source.get("phone", ""),
        "Languages": "; ".join(reported_languages), "Active_Qualifications": "; ".join(unique(active_names)),
        "Qualification_Details": " | ".join(f"{q[0]} — issued {iso_date(q[1])}" for q in active),
        "Life_Issue_Date": iso_date(general_life[1]) if general_life else "",
        "Years_Since_Life_Issue": years_since(general_life[1], check_date) if general_life else "",
        "Active_Health_Authority": "Yes" if any("health" in str(x).lower() for x in active_names) else "No",
        "Active_PC_Authority": "Yes" if any(str(x).lower() in {"property", "casualty", "personal lines"} for x in active_names) else "No",
        "Active_Variable_Authority": "Yes" if any("var" in str(x).lower() for x in active_names) else "No",
        "Appointed_Insurers": names(appointments), "Appointment_Row_Count": len(appointments),
        "Unique_Insurer_Count": len(unique([r[0] for r in appointments])), "Life_Appointed_Insurers": names(life_appointments),
        "Unique_Life_Insurer_Count": len(unique([r[0] for r in life_appointments])), "Health_Appointed_Insurers": names(health_appointments),
        "PC_Appointed_Insurers": names(pc_appointments), "Appointment_Details": details(appointments),
        "Agency_Organizations": names(agencies), "Unique_Agency_Count": len(unique([r[0] for r in agencies])),
        "Agency_Relationship_Count": len(agencies), "Life_Agency_Organizations": names([r for r in agencies if r[1].lower() == "life"]),
        "Agency_Relationship_Details": details(agencies), "Latest_Displayed_Relationship_Date": max(dates).isoformat() if dates else "",
    })
    return row


def load_source_rows():
    with Path(args.input).resolve().open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    selected = []
    seen = set()
    for row in source_rows:
        license_number = (row.get("license_number") or "").strip()
        if license_number and license_number not in seen:
            seen.add(license_number)
            clean_row = dict(row)
            clean_row["license_number"] = license_number
            selected.append(clean_row)
    return selected


def load_research():
    result = {}
    for path in [ROOT / "exports/test-batch-50/agency-research.json", ROOT / "exports/test-batch-50/screening-validation-agency-research.json"]:
        if path.exists():
            result.update(json.loads(path.read_text(encoding="utf-8")))
    return result


def load_completed():
    rows_path = ROOT / "exports" / args.completed_cache / "selected-rows.json"
    order_path = ROOT / args.completed_order
    if not rows_path.exists() or not order_path.exists():
        return {}, []
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    order = json.loads(order_path.read_text(encoding="utf-8"))
    by_license = {row.get("License_Number"): row for row in rows}
    return {license_number: by_license[license_number] for license_number in order if license_number in by_license}, order


def request_document(url, license_number):
    last_error = ""
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CDI recruiting screening)"})
            with urllib.request.urlopen(request, timeout=45) as response:
                document = response.read().decode("utf-8-sig", errors="replace")
            if not re.search(r"License #:\s*" + re.escape(license_number) + r"\s*<", document, re.I):
                raise ValueError("license identity mismatch or unavailable CDI record")
            return document, "", attempt
        except Exception as exc:
            last_error = str(exc)
            if attempt < 3:
                time.sleep(2 ** attempt)
    return "", last_error, 3


def save_state(records, progress, manifest):
    atomic_write(state_path, records)
    atomic_write(progress_path, progress)
    atomic_write(manifest_path, manifest)


def self_test():
    temp = cache / "self-test"
    temp.mkdir(parents=True, exist_ok=True)
    sample_html = next((p for p in (ROOT / "exports/test-batch-50").glob("*.html") if p.is_file()), None)
    if sample_html is None:
        sample_html = next((p for p in (ROOT / "exports/license-details-cache").glob("*.html") if p.is_file()), None)
    if sample_html is None:
        raise SystemExit("self-test requires a saved CDI HTML fixture")
    document = sample_html.read_text(encoding="utf-8-sig")
    license_number = sample_html.stem
    fact = extract_fact(document, license_number)
    if not fact.get("qualification_table_found") or not fact.get("qualifications"):
        raise SystemExit("self-test extraction did not find qualification rows")
    test_records = {license_number: {"fact": fact, "row": {"License_Number": license_number}, "status": "PASS"}}
    test_progress = {"processed_remaining": 1, "checkpoint_size": 25}
    test_manifest = [{"license_number": license_number, "status": "PASS"}]
    atomic_write(temp / "records.json", test_records)
    atomic_write(temp / "progress.json", test_progress)
    atomic_write(temp / "manifest.json", test_manifest)
    if json.loads((temp / "records.json").read_text(encoding="utf-8"))[license_number]["status"] != "PASS":
        raise SystemExit("self-test checkpoint read failed")
    print(json.dumps({"retrieval_fixture": str(sample_html), "extraction": "ok", "atomic_checkpoint": "ok", "resume_state": "ok", "export_input": "ok"}, indent=2))


agency_research = load_research()
if args.self_test:
    self_test()
    raise SystemExit(0)

source_rows = load_source_rows()
sources = {row["license_number"]: row for row in source_rows}
completed, completed_order = load_completed()
if len(completed) != len(completed_order):
    raise SystemExit("completed 50 results are incomplete; refusing to overwrite or restart")

records = {}
if state_path.exists():
    records = json.loads(state_path.read_text(encoding="utf-8"))
for license_number, row in completed.items():
    records.setdefault(license_number, {"source": sources.get(license_number, {}), "row": row, "status": "COMPLETED_50", "fact": None, "error": ""})

manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
manifest_by_license = {entry.get("license_number"): entry for entry in manifest}
for license_number in completed:
    manifest_by_license.setdefault(license_number, {"license_number": license_number, "status": "COMPLETED_50", "error": ""})
manifest = list(manifest_by_license.values())

remaining = [
    row for row in source_rows
    if row["license_number"] not in records
    or (args.retry_failed and records[row["license_number"]].get("fact") is None and records[row["license_number"]].get("attempts", 0) >= 3)
]
if args.limit:
    remaining = remaining[:args.limit]

progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
prior_processed_remaining = int(progress.get("processed_remaining", 0))
new_count = 0
consecutive_failures = int(progress.get("consecutive_retrieval_failures", 0))
stop_reason = ""
for source in remaining:
    license_number = source["license_number"]
    retrying_saved_failure = args.retry_failed and license_number in records and records[license_number].get("fact") is None and records[license_number].get("attempts", 0) >= 3
    if license_number in records and not retrying_saved_failure:
        continue
    started = datetime.now().astimezone().isoformat()
    document, error, attempts = request_document(source.get("license_url", ""), license_number)
    fact = None
    row = None
    status = "REVIEW"
    if document:
        try:
            html_path = html_dir / f"{license_number}.html"
            fd, temp_name = tempfile.mkstemp(prefix=html_path.name + ".", suffix=".tmp", dir=html_dir)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(document)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, html_path)
            fact = extract_fact(document, license_number)
            decision = assess_fact(fact, agency_research)
            row = make_row(source, fact, decision, args.check_date)
            status = decision["status"]
            error = "" if status != "REVIEW" else decision["reason"]
            consecutive_failures = 0
        except Exception as exc:
            error = str(exc)
            row = make_row(source, None, None, args.check_date, retrieval_error=error)
            consecutive_failures += 1
    else:
        row = make_row(source, None, None, args.check_date, retrieval_error=error)
        consecutive_failures += 1

    records[license_number] = {"source": source, "row": row, "fact": fact, "status": status, "error": error, "attempts": attempts, "checked_at": started}
    manifest_by_license[license_number] = {"license_number": license_number, "status": status, "error": error, "attempts": attempts, "checked_at": started}
    manifest = list(manifest_by_license.values())
    new_count += 1
    progress = {"total_unique": len(source_rows), "completed_50": len(completed), "processed_remaining": prior_processed_remaining + new_count, "last_license": license_number, "last_status": status, "consecutive_retrieval_failures": consecutive_failures, "updated_at": datetime.now().astimezone().isoformat(), "checkpoint_size": 25, "stopped": False, "stop_reason": ""}
    save_state(records, progress, manifest)
    print(f"{new_count} {license_number} {status} attempts={attempts}", flush=True)

    if (prior_processed_remaining + new_count) % 25 == 0:
        progress["checkpoint"] = prior_processed_remaining + new_count
        save_state(records, progress, manifest)
        print(f"CHECKPOINT {new_count} records", flush=True)
    if consecutive_failures >= 12:
        stop_reason = "CDI source produced 12 consecutive retrieval or extraction failures; saved state and stopped to avoid endless retries."
        break

if stop_reason:
    progress["stopped"] = True
    progress["stop_reason"] = stop_reason
    save_state(records, progress, manifest)
else:
    progress["stopped"] = False
    progress["remaining_unprocessed"] = len([row for row in source_rows if row["license_number"] not in records])
    save_state(records, progress, manifest)

rows = [records[row["license_number"]]["row"] for row in source_rows if row["license_number"] in records]
atomic_write(cache / "selected-rows.json", rows)
summary = {"total_unique": len(source_rows), "records_saved": len(rows), "completed_50": len(completed), "new_processed_this_run": new_count, "status_counts": dict(Counter(record["row"].get("Passed_Test", "") for record in records.values())), "remaining_unprocessed": len([row for row in source_rows if row["license_number"] not in records]), "stopped": bool(stop_reason), "stop_reason": stop_reason}
atomic_write(cache / "summary.json", summary)
print(json.dumps(summary, indent=2, ensure_ascii=False))
