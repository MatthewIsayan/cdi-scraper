"""Exercise qualification-data routing without modifying real evidence."""
from screening_logic import assess_fact


base = {"license": "SIM", "expected_license": "SIM", "appointments": "", "agencies": "", "orders": ""}
cases = {
    "absent": dict(base),
    "null": {**base, "qualifications": None},
    "empty_list": {**base, "qualifications": []},
    "malformed_rows": {**base, "qualifications": [["Life", "01/01/2020"]]},
    "verified_burial_only": {**base, "qualifications": [["Life Limited-Funeral & Burial", "01/01/2020", "Active"]]},
}
results = {name: assess_fact(fact, {}) for name, fact in cases.items()}
expected_review = {name: result["status"] == "REVIEW" and result["passed_test"] == "" for name, result in results.items() if name != "verified_burial_only"}
burial_preserved = results["verified_burial_only"]["status"] == "FAIL" and results["verified_burial_only"]["passed_test"] == "No"
output = {"cases": results, "all_missing_or_malformed_review": all(expected_review.values()), "burial_only_failure_preserved": burial_preserved, "real_evidence_modified": False}
print(output)
if not output["all_missing_or_malformed_review"] or not burial_preserved:
    raise SystemExit(1)
