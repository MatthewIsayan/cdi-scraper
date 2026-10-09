"""Validate the saved first-60 evidence and output against the reference CSV."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "output/csv/cdi-agents-selected-columns-first-60-enriched.csv"
SAVED = ROOT / "exports/next-fifty-test/selected-rows.json"
OUT = ROOT / "exports/test-batch-50/validation-60.json"

with REF.open(encoding="utf-8-sig", newline="") as f:
    reference = list(csv.DictReader(f))[:60]
saved_all = json.loads(SAVED.read_text(encoding="utf-8"))
saved = saved_all[:60]
columns = list(reference[0]) if reference else []


def comparable(value):
    return "" if value is None else str(value)

row_diffs = []
for i, (ref, got) in enumerate(zip(reference, saved), start=1):
    diffs = {c: {"reference": ref.get(c, ""), "saved": got.get(c, "")} for c in columns if comparable(ref.get(c, "")) != comparable(got.get(c, ""))}
    if diffs:
        row_diffs.append({"row": i, "license_number": ref.get("License_Number", ""), "differences": diffs})

sequence_differences = []
for i, (ref, got) in enumerate(zip(reference, saved), start=1):
    if ref.get("License_Number") != got.get("License_Number"):
        sequence_differences.append({"row": i, "reference": ref.get("License_Number", ""), "saved": got.get("License_Number", "")})

facts = []
for rel in ("first-ten-test", "next-fifty-test"):
    data = json.loads((ROOT / "exports" / rel / "facts.json").read_text(encoding="utf-8"))
    facts.extend(item.get("facts", {}) | {"input": item.get("input", {}), "error": item.get("error", "")} for item in data)
facts_by_license = {item.get("input", {}).get("license_number", ""): item for item in facts}

derived_mismatches = []
for i, row in enumerate(saved, start=1):
    license_number = row.get("License_Number", "")
    fact = facts_by_license.get(license_number, {})
    if not fact:
        derived_mismatches.append({"row": i, "license_number": license_number, "reason": "missing saved fact"})
        continue
    appointments = fact.get("appointments", [])
    agencies = fact.get("agencies", [])
    unique_insurers = {r[0] for r in appointments if len(r) >= 1}
    life_insurers = {r[0] for r in appointments if len(r) >= 2 and r[1].lower() == "life"}
    derived = {
        "Appointment_Row_Count": str(len(appointments)),
        "Unique_Insurer_Count": str(len(unique_insurers)),
        "Unique_Life_Insurer_Count": str(len(life_insurers)),
        "Agency_Relationship_Count": str(len(agencies)),
        "Unique_Agency_Count": str(len({r[0] for r in agencies if r})),
    }
    for field, expected in derived.items():
        if comparable(row.get(field, "")) != comparable(expected):
            derived_mismatches.append({"row": i, "license_number": license_number, "field": field, "reference_value": row.get(field, ""), "recomputed_value": expected})

result = {
    "reference_rows_checked": len(reference),
    "saved_rows_checked": len(saved),
    "reference_columns": len(columns),
    "sequence_differences": sequence_differences,
    "row_differences": row_diffs,
    "difference_counts_by_column": dict(Counter(field for item in row_diffs for field in item["differences"])),
    "derived_count_mismatches": derived_mismatches,
    "interpretation": "No saved-output differences; the first 60 reference rows match the saved selected rows and recomputed appointment/agency counts." if not row_diffs and not sequence_differences and not derived_mismatches else "Differences require investigation; no values were forced to match.",
}
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({
    "reference_rows_checked": len(reference),
    "saved_rows_checked": len(saved),
    "row_difference_count": len(row_diffs),
    "sequence_difference_count": len(sequence_differences),
    "derived_count_mismatch_count": len(derived_mismatches),
    "difference_counts_by_column": result["difference_counts_by_column"],
}, indent=2))
