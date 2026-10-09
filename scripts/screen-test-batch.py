"""Merge browser-extracted facts, apply the finalized rules, and build rows."""
import argparse
import csv
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from screening_logic import assess_fact

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--cache", default="test-batch-50")
parser.add_argument("--check-date", default="2026-10-08")
parser.add_argument("--license-order", default="")
args = parser.parse_args()
cache = ROOT / "exports" / args.cache


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


with Path(args.input).resolve().open(encoding="utf-8-sig", newline="") as f:
    source_rows = list(csv.DictReader(f))
if args.license_order:
    requested_licenses = json.loads(Path(args.license_order).read_text(encoding="utf-8"))
    source_by_license = {(row.get("license_number") or "").strip(): row for row in source_rows}
    selected = [source_by_license[license_number] for license_number in requested_licenses if license_number in source_by_license]
else:
    selected = []
    seen = set()
    for row in source_rows:
        license_number = (row.get("license_number") or "").strip()
        if license_number and license_number not in seen:
            seen.add(license_number)
            selected.append(row)
            if len(selected) >= 50:
                break

browser_facts = {}
for path in sorted(cache.glob("browser-facts-*.json")):
    for fact in json.loads(path.read_text(encoding="utf-8")):
        browser_facts[fact["license_number"]] = fact
agency_research = json.loads((cache / "agency-research.json").read_text(encoding="utf-8"))

columns = [
    "Name", "Passed_Test", "Assessment", "License_URL", "License_Number", "Business_Address", "Business_Phone",
    "Directions_URL", "Source_ZIPs", "Checked_On", "Languages", "Active_Qualifications", "Qualification_Details",
    "Life_Issue_Date", "Years_Since_Life_Issue", "Active_Health_Authority", "Active_PC_Authority", "Active_Variable_Authority",
    "Appointed_Insurers", "Appointment_Row_Count", "Unique_Insurer_Count", "Life_Appointed_Insurers", "Unique_Life_Insurer_Count",
    "Health_Appointed_Insurers", "PC_Appointed_Insurers", "Appointment_Details", "Agency_Organizations", "Unique_Agency_Count",
    "Agency_Relationship_Count", "Life_Agency_Organizations", "Agency_Relationship_Details", "Latest_Displayed_Relationship_Date", "Rule_Document"
]

rows = []
audit = []
for source in selected:
    license_number = source["license_number"].strip()
    fact = browser_facts.get(license_number)
    row = {c: "" for c in columns}
    row.update({
        "Name": source["name"],
        "License_URL": source["license_url"],
        "License_Number": license_number,
        "Business_Address": source.get("address", ""),
        "Business_Phone": source.get("phone", ""),
        "Directions_URL": source.get("directions_url", ""),
        "Source_ZIPs": source.get("source_zips", ""),
        "Checked_On": args.check_date,
        "Rule_Document": "imo-final-approval-rules.md (2026-10-08)",
    })
    if not fact or fact.get("license") != license_number:
        row["Assessment"] = "Needs review: CDI page was unavailable or did not verify this license number; no rejection inferred."
        audit.append({"license_number": license_number, "status": "REVIEW", "reason": row["Assessment"]})
        rows.append(row)
        continue

    qualifications = fact.get("qualifications", [])
    if not isinstance(qualifications, list):
        qualifications = []
    appointments = parse_relationships(fact.get("appointments", ""))
    agencies = parse_relationships(fact.get("agencies", ""))
    orders = parse_orders(fact.get("orders", ""))
    active = [q for q in qualifications if isinstance(q, (list, tuple)) and len(q) >= 3 and str(q[2]).lower() == "active"]
    active_names = [q[0] for q in active]
    general_life = next((q for q in active if q[0].lower() == "life"), None)
    decision_fact = dict(fact)
    decision_fact["expected_license"] = license_number
    decision = assess_fact(decision_fact, agency_research)
    status = decision["status"]
    passed = decision["passed_test"]
    reason = decision["reason"]
    exclusion_reasons = decision.get("exclusions", [])
    unknown_agencies = decision.get("unknown_agencies", [])

    reported_languages = unique([x.strip() for x in re.split(r"[,;]", fact.get("languages", "")) if x.strip()])
    active_appointment = [r for r in appointments if r and len(r) >= 3]
    life_appointments = [r for r in appointments if len(r) >= 2 and r[1].lower() == "life"]
    health_appointments = [r for r in appointments if len(r) >= 2 and "health" in r[1].lower()]
    pc_appointments = [r for r in appointments if len(r) >= 2 and r[1].lower() in {"property", "casualty", "personal lines"}]
    dates = [datetime.strptime(r[2], "%m/%d/%Y").date() for r in appointments + agencies if len(r) >= 3 and r[2]]
    row.update({
        "Name": source["name"],
        "Passed_Test": passed,
        "Assessment": reason,
        "Business_Address": fact.get("business_address") or source.get("address", ""),
        "Business_Phone": fact.get("business_phone") or source.get("phone", ""),
        "Languages": "; ".join(reported_languages),
        "Active_Qualifications": "; ".join(unique(active_names)),
        "Qualification_Details": " | ".join(f"{q[0]} — issued {iso_date(q[1])}" for q in active),
        "Life_Issue_Date": iso_date(general_life[1]) if general_life else "",
        "Years_Since_Life_Issue": years_since(general_life[1], args.check_date) if general_life else "",
        "Active_Health_Authority": "Yes" if any("health" in x.lower() for x in active_names) else "No",
        "Active_PC_Authority": "Yes" if any(x.lower() in {"property", "casualty", "personal lines"} for x in active_names) else "No",
        "Active_Variable_Authority": "Yes" if any("var" in x.lower() for x in active_names) else "No",
        "Appointed_Insurers": names(appointments),
        "Appointment_Row_Count": len(appointments),
        "Unique_Insurer_Count": len(unique([r[0] for r in appointments])),
        "Life_Appointed_Insurers": names(life_appointments),
        "Unique_Life_Insurer_Count": len(unique([r[0] for r in life_appointments])),
        "Health_Appointed_Insurers": names(health_appointments),
        "PC_Appointed_Insurers": names(pc_appointments),
        "Appointment_Details": details(appointments),
        "Agency_Organizations": names(agencies),
        "Unique_Agency_Count": len(unique([r[0] for r in agencies])),
        "Agency_Relationship_Count": len(agencies),
        "Life_Agency_Organizations": names([r for r in agencies if r[1].lower() == "life"]),
        "Agency_Relationship_Details": details(agencies),
        "Latest_Displayed_Relationship_Date": max(dates).isoformat() if dates else "",
    })
    audit.append({"license_number": license_number, "status": status, "passed_test": passed, "exclusions": exclusion_reasons, "unknown_agencies": unknown_agencies, "orders": orders, "appointment_rows": len(appointments), "agency_rows": len(agencies), "license_url": source["license_url"], "checked_on": args.check_date})
    rows.append(row)

(cache / "facts.json").write_text(json.dumps([browser_facts[r["license_number"]] for r in selected if r["license_number"] in browser_facts], indent=2, ensure_ascii=False), encoding="utf-8")
(cache / "selected-rows.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
(cache / "screening-audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"rows": len(rows), "columns": len(columns), "status_counts": dict(Counter(x["status"] for x in audit)), "passed_test_counts": dict(Counter(r["Passed_Test"] for r in rows)), "unknown_agencies": sorted({x for a in audit for x in a.get("unknown_agencies", [])}), "licenses": unique([r["License_Number"] for r in rows])}, indent=2, ensure_ascii=False))
