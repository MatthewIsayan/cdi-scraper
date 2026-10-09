"""Verify the final full-batch workbook against the saved row state."""
import csv
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "outputs/full-batch/cdi-agents-full-batch.xlsx"
ROWS = json.loads((ROOT / "exports/full-batch/selected-rows.json").read_text(encoding="utf-8"))
OUT = ROOT / "exports/full-batch/workbook-verification.json"
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def cell_value(cell, shared):
    node = cell.find("x:v", NS)
    value = "" if node is None else (node.text or "")
    if cell.attrib.get("t") == "s" and value.isdigit():
        return shared[int(value)]
    return value


def sheet_data(zf, target, shared):
    root = ET.fromstring(zf.read(target))
    rows = root.findall(".//x:sheetData/x:row", NS)
    values, formulas = [], []
    for row in rows:
        row_values, row_formulas = {}, {}
        for cell in row.findall("x:c", NS):
            ref = cell.attrib.get("r", "")
            col = "".join(ch for ch in ref if ch.isalpha())
            row_values[col] = cell_value(cell, shared)
            formula = cell.find("x:f", NS)
            if formula is not None:
                row_formulas[col] = formula.text or ""
        values.append(row_values)
        formulas.append(row_formulas)
    return values, formulas


def col_letter(index):
    n = index + 1
    result = ""
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def safe_language_sheet(language):
    return f"Passed - {language}"[:31]


with Path(ROOT / "ROUND-2-ENGLISH/exports/cdi-agents.csv").open(encoding="utf-8-sig", newline="") as handle:
    source_by_license = {row["license_number"].strip(): row for row in csv.DictReader(handle)}

with zipfile.ZipFile(XLSX) as zf:
    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall("x:si", NS):
            shared.append("".join(node.text or "" for node in si.iter() if node.tag.endswith("}t")))
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheets = []
    for sheet in workbook.findall("x:sheets/x:sheet", NS):
        rid = sheet.attrib[f"{{{NS['r']}}}id"]
        target = rel_map[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        values, formulas = sheet_data(zf, target, shared)
        sheets.append({"name": sheet.attrib["name"], "values": values, "formulas": formulas})

expected_status = Counter((row.get("Passed_Test") or "Needs review") for row in ROWS)
expected_languages = {}
for row in ROWS:
    if row.get("Passed_Test") == "Yes":
        for language in (x.strip() for x in (row.get("Languages") or "").split(";")):
            if language:
                expected_languages.setdefault(language, set()).add(row["License_Number"])

master = next(sheet for sheet in sheets if sheet["name"] == "Master")
headers = [master["values"][0].get(col_letter(i), "") for i in range(33)]
sheet_counts = {sheet["name"]: len(sheet["values"]) - 1 for sheet in sheets}
license_sets = {sheet["name"]: {row.get("E", "") for row in sheet["values"][1:] if row.get("E", "")} for sheet in sheets}
formula_checks, link_mismatches = {}, []
for sheet in sheets:
    formula_count = 0
    for row_number, (row, formula_row) in enumerate(zip(sheet["values"][1:], sheet["formulas"][1:]), start=2):
        formula = formula_row.get("D", "")
        license_number = row.get("E", "")
        expected_url = source_by_license.get(license_number, {}).get("license_url", "")
        if "HYPERLINK" in formula.upper():
            formula_count += 1
        if expected_url and (expected_url not in formula or license_number not in formula):
            link_mismatches.append({"sheet": sheet["name"], "row": row_number, "license": license_number, "expected_url": expected_url, "formula": formula})
    formula_checks[sheet["name"]] = {"license_url_formula_count": formula_count, "license_url_formula_count_expected": len(sheet["values"]) - 1}

actual_status = {"Passed": sheet_counts["Passed"], "Failed": sheet_counts["Failed"], "Needs review": sheet_counts["Needs review"]}
language_checks = {}
passed_licenses = license_sets["Passed"]
for language, expected in expected_languages.items():
    sheet_name = safe_language_sheet(language)
    actual = license_sets.get(sheet_name, set())
    language_checks[sheet_name] = {"expected_count": len(expected), "actual_count": len(actual), "exact_match": actual == expected, "only_passed": actual.issubset(passed_licenses)}

result = {
    "xlsx": str(XLSX), "sheet_names": [sheet["name"] for sheet in sheets], "first_four_columns": headers[:4],
    "column_count": len(headers), "master_data_rows": sheet_counts["Master"], "master_unique_licenses": len(license_sets["Master"]),
    "expected_unique_licenses": len({row["License_Number"] for row in ROWS}), "status_expected": dict(expected_status),
    "status_actual": actual_status, "status_reconciles": actual_status == {"Passed": expected_status["Yes"], "Failed": expected_status["No"], "Needs review": expected_status["Needs review"]},
    "language_checks": language_checks, "license_formula_checks": formula_checks, "license_link_mismatches": link_mismatches[:20],
    "license_links_match": not link_mismatches,
}
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(result, indent=2, ensure_ascii=False))
if not result["status_reconciles"] or result["master_data_rows"] != result["expected_unique_licenses"] or result["master_unique_licenses"] != result["expected_unique_licenses"] or not result["license_links_match"] or any(not check["exact_match"] or not check["only_passed"] for check in language_checks.values()):
    raise SystemExit(1)
