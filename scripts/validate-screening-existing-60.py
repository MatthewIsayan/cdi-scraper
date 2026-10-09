"""Run the current screening logic against saved evidence for the 60-agent reference."""
import csv
import json
from collections import Counter
from pathlib import Path

from screening_logic import assess_fact

ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "output/csv/cdi-agents-selected-columns-first-60-enriched.csv"
OUT_PATH = ROOT / "exports/test-batch-50/screening-validation-existing-60.json"

with REF_PATH.open(encoding="utf-8-sig", newline="") as handle:
    reference_rows = list(csv.DictReader(handle))[:60]

saved_records = []
for batch in ("first-ten-test", "next-fifty-test"):
    saved_records.extend(json.loads((ROOT / "exports" / batch / "facts.json").read_text(encoding="utf-8")))
by_license = {record["input"]["license_number"]: record for record in saved_records}
agency_research = json.loads((ROOT / "exports/next-fifty-test/agency-research.json").read_text(encoding="utf-8"))
agency_research.update(json.loads((ROOT / "exports/test-batch-50/screening-validation-agency-research.json").read_text(encoding="utf-8")))

results = []
for reference in reference_rows:
    license_number = reference["License_Number"]
    record = by_license.get(license_number)
    if record is None:
        decision = assess_fact({"expected_license": license_number, "retrieval_error": "saved evidence missing"}, agency_research)
    else:
        raw_fact = record.get("facts")
        fact = dict(raw_fact) if isinstance(raw_fact, dict) else {}
        fact["license"] = license_number
        fact["expected_license"] = license_number
        if record.get("error"):
            fact["retrieval_error"] = record["error"]
        decision = assess_fact(fact, agency_research)
    expected = reference.get("Passed_Test", "")
    actual = decision["passed_test"]
    results.append({
        "license_number": license_number,
        "name": reference.get("Name", ""),
        "reference_passed_test": expected,
        "new_passed_test": actual,
        "new_status": decision["status"],
        "matched": expected == actual,
        "reason": decision["reason"],
        "exclusions": decision.get("exclusions", []),
        "unknown_agencies": decision.get("unknown_agencies", []),
        "orders": decision.get("orders", []),
    })

# A synthetic missing-table record tests the safeguard without modifying any real evidence.
simulated_missing_table = {
    "license": "SIM-MISSING-QUALIFICATIONS",
    "expected_license": "SIM-MISSING-QUALIFICATIONS",
    "appointments": "",
    "agencies": "",
    "orders": "",
}
simulated_decision = assess_fact(simulated_missing_table, {})
safeguard_worked = simulated_decision["status"] == "REVIEW" and simulated_decision["passed_test"] == ""

diffs = [item for item in results if not item["matched"]]
output = {
    "reference_agents_checked": len(reference_rows),
    "saved_evidence_records": len(saved_records),
    "decision_match": len(diffs) == 0,
    "decision_counts_reference": dict(Counter(item["reference_passed_test"] or "REVIEW" for item in results)),
    "decision_counts_new": dict(Counter(item["new_passed_test"] or "REVIEW" for item in results)),
    "differences": diffs,
    "all_results": results,
    "simulated_missing_qualification_table": {
        "decision": simulated_decision,
        "safeguard_worked": safeguard_worked,
        "real_evidence_modified": False,
    },
}
OUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({
    "reference_agents_checked": len(reference_rows),
    "saved_evidence_records": len(saved_records),
    "decision_match": output["decision_match"],
    "difference_count": len(diffs),
    "decision_counts_reference": output["decision_counts_reference"],
    "decision_counts_new": output["decision_counts_new"],
    "safeguard_worked": safeguard_worked,
}, indent=2, ensure_ascii=False))
