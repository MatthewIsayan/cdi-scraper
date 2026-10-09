"""Shared decision logic for CDI producer screening."""
import re
from collections import Counter


def unique(values):
    return list(dict.fromkeys(values))


def parse_relationships(value):
    """Return (rows, parse_ok) for compact pipe-delimited relationship data."""
    if value in (None, ""):
        return [], value == ""
    if isinstance(value, list):
        rows = []
        for item in value:
            if not isinstance(item, (list, tuple)) or len(item) < 3 or any(x is None for x in item[:3]):
                return [], False
            rows.append(list(item[:3]))
        return rows, True
    if not isinstance(value, str):
        return [], False
    rows = []
    for item in value.split("|"):
        parts = item.split("~")
        if len(parts) != 3 or any(not part.strip() for part in parts):
            return [], False
        rows.append(parts)
    return rows, True


def parse_orders(value):
    if value in (None, ""):
        return [], value == ""
    if isinstance(value, list):
        rows = []
        for item in value:
            if not isinstance(item, (list, tuple)) or not item:
                return [], False
            rows.append(list(item))
        return rows, True
    if not isinstance(value, str):
        return [], False
    rows = []
    for item in value.split("|"):
        parts = item.rsplit("~", 1)
        if len(parts) != 2 or not parts[0].strip():
            return [], False
        rows.append(parts)
    return rows, True


def _agency_is_excluded(name, agency_research):
    entry = agency_research.get(name, {})
    decision = str(entry.get("decision", "")).lower()
    classification = str(entry.get("classification", "")).lower()
    if decision:
        return "bank/securities" in decision and "eligible" not in decision
    return "bank/securities" in classification and "not verified" not in classification


def _agency_is_known_eligible(name):
    normalized = str(name).upper().strip()
    return (
        "WORLD FINANCIAL GROUP" in normalized
        or "PRIMERICA FINANCIAL SERVICES INSURANCE MARKETING" in normalized
        or normalized == "CALIFORNIA HEALTH BENEFIT EXCHANGE"
        or normalized == "AAA LIFE AGENCY LLC"
        or normalized == "AUTOMOBILE CLUB OF SOUTHERN CALIFORNIA"
    )


def assess_fact(fact, agency_research):
    """Assess one normalized compact fact record.

    Missing, unavailable, or malformed qualification evidence always returns
    REVIEW. A no-Life FAIL is only emitted after a valid qualification table
    has been parsed successfully.
    """
    if not isinstance(fact, dict):
        return {"status": "REVIEW", "passed_test": "", "reason": "Needs review: CDI evidence is unavailable or malformed; no rejection inferred.", "exclusions": [], "unknown_agencies": [], "orders": []}
    if fact.get("retrieval_error"):
        return {"status": "REVIEW", "passed_test": "", "reason": "Needs review: CDI evidence was unavailable; no rejection inferred.", "exclusions": [], "unknown_agencies": [], "orders": []}
    license_number = str(fact.get("license", "")).strip()
    expected_license = str(fact.get("expected_license", "")).strip()
    if expected_license and license_number != expected_license:
        return {"status": "REVIEW", "passed_test": "", "reason": "Needs review: CDI evidence did not verify the requested license number; no rejection inferred.", "exclusions": [], "unknown_agencies": [], "orders": []}

    qualifications = fact.get("qualifications")
    if qualifications is None or not isinstance(qualifications, list) or not qualifications:
        return {"status": "REVIEW", "passed_test": "", "reason": "Needs review: qualification data is missing or unavailable; no rejection inferred.", "exclusions": [], "unknown_agencies": [], "orders": []}
    parsed_qualifications = []
    for qualification in qualifications:
        if not isinstance(qualification, (list, tuple)) or len(qualification) < 3 or any(x is None for x in qualification[:3]) or not str(qualification[0]).strip() or not str(qualification[2]).strip():
            return {"status": "REVIEW", "passed_test": "", "reason": "Needs review: qualification data could not be parsed; no rejection inferred.", "exclusions": [], "unknown_agencies": [], "orders": []}
        parsed_qualifications.append(list(qualification))

    appointments, appointments_ok = parse_relationships(fact.get("appointments", ""))
    agencies, agencies_ok = parse_relationships(fact.get("agencies", ""))
    orders, orders_ok = parse_orders(fact.get("orders", ""))
    if not appointments_ok or not agencies_ok or not orders_ok:
        return {"status": "REVIEW", "passed_test": "", "reason": "Needs review: CDI relationship or order data could not be parsed; no rejection inferred.", "exclusions": [], "unknown_agencies": [], "orders": orders}

    active = [q for q in parsed_qualifications if str(q[2]).lower() == "active"]
    active_names = [str(q[0]) for q in active]
    general_life = next((q for q in active if str(q[0]).lower() == "life"), None)
    life_limited = [q for q in active if "limited" in str(q[0]).lower() or "funeral" in str(q[0]).lower() or "burial" in str(q[0]).lower()]
    current_relationship_names = [r[0] for r in appointments + agencies]
    named_exclusions = unique([name for name in current_relationship_names if re.search(r"\bSTATE FARM\b|\bFARMERS\b|\bALLSTATE\b|\bKNIGHTS OF COLUMBUS\b|\bTHRIVENT\b", name, re.I)])
    researched_exclusions = unique([name for name in [r[0] for r in agencies] if _agency_is_excluded(name, agency_research)])
    unknown_agencies = unique([name for name in [r[0] for r in agencies] if name not in agency_research and not _agency_is_known_eligible(name)])
    exclusion_reasons = named_exclusions + researched_exclusions

    if orders:
        status, passed, reason = "REVIEW", "", "Needs review: CDI displays a material licensing order; current terms and contracting impact require review."
    elif not general_life:
        status, passed = "FAIL", "No"
        reason = "No active general Life qualification displayed; active authority is limited funeral/burial Life only." if life_limited else "No active general Life qualification displayed."
    elif exclusion_reasons:
        status, passed = "FAIL", "No"
        reason = "Current excluded relationship displayed: " + "; ".join(name.rstrip(".") for name in exclusion_reasons) + "."
    elif unknown_agencies:
        status, passed, reason = "REVIEW", "", "Needs review: agency classification is unresolved for " + "; ".join(unknown_agencies) + "."
    else:
        status, passed = "PASS", "Yes"
        life_agencies = [r[0] for r in agencies if str(r[1]).lower() == "life"]
        life_insurers = unique([r[0] for r in appointments if str(r[1]).lower() == "life"])
        if life_agencies:
            context = "Life agency relationship: " + "; ".join(unique(life_agencies))
        elif life_insurers:
            context = "Life appointments: " + "; ".join(life_insurers[:3]) + ("; additional insurers listed" if len(life_insurers) > 3 else "")
        elif not appointments and not agencies:
            context = "no displayed agency or insurer relationships; lower priority"
        else:
            context = "only non-Life or lower-priority relationships displayed"
        reason = "Active general Life; " + context + "; no confirmed exclusion."
    return {"status": status, "passed_test": passed, "reason": reason, "exclusions": exclusion_reasons, "unknown_agencies": unknown_agencies, "orders": orders, "active_names": active_names, "general_life": general_life, "qualifications": parsed_qualifications, "appointments": appointments, "agencies": agencies}


def counter_status(results):
    return dict(Counter(result["status"] for result in results))
