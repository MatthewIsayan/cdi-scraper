"""Verify workbook structure, reconciliation, language subsets, and license formulas."""
import json
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "outputs/test-batch-50/cdi-agents-test-batch-50.xlsx"
ROWS = json.loads((ROOT / "exports/test-batch-50/selected-rows.json").read_text(encoding="utf-8"))
OUT = ROOT / "exports/test-batch-50/workbook-verification.json"
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def cell_value(cell):
    node = cell.find("x:v", NS)
    return "" if node is None else (node.text or "")


def sheet_data(zf, target):
    root = ET.fromstring(zf.read(target))
    rows = root.findall(".//x:sheetData/x:row", NS)
    values = []
    formulas = []
    for row in rows:
        row_values = {}
        row_formulas = {}
        for cell in row.findall("x:c", NS):
            ref = cell.attrib.get("r", "")
            col = "".join(ch for ch in ref if ch.isalpha())
            row_values[col] = cell_value(cell)
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


with zipfile.ZipFile(XLSX) as zf:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheets = []
    for sheet in workbook.findall("x:sheets/x:sheet", NS):
        rid = sheet.attrib[f"{{{NS['r']}}}id"]
        target = rel_map[rid]
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        values, formulas = sheet_data(zf, target)
        sheets.append({"name": sheet.attrib["name"], "target": target, "values": values, "formulas": formulas})

expected_status = Counter((row["Passed_Test"] or "Needs review") for row in ROWS)
expected_languages = {}
for row in ROWS:
    if row["Passed_Test"] == "Yes":
        for language in (x.strip() for x in (row.get("Languages") or "").split(";")):
            if language:
                expected_languages.setdefault(language, set()).add(row["License_Number"])

master = next(sheet for sheet in sheets if sheet["name"] == "Master")
headers = [master["values"][0].get(col_letter(i), "") for i in range(33)]
sheet_counts = {sheet["name"]: len(sheet["values"]) - 1 for sheet in sheets}
license_sets = {}
formula_checks = {}
for sheet in sheets:
    license_sets[sheet["name"]] = {row.get("E", "") for row in sheet["values"][1:] if row.get("E", "")}
    formula_checks[sheet["name"]] = {
        "license_url_formula_count": sum(1 for row in sheet["formulas"][1:] if "HYPERLINK" in row.get("D", "").upper()),
        "license_url_formula_count_expected": len(sheet["values"]) - 1,
    }

actual_status = {"Passed": sheet_counts["Passed"], "Failed": sheet_counts["Failed"], "Needs review": sheet_counts["Needs review"]}
language_checks = {}
for language, expected in expected_languages.items():
    sheet_name = f"Passed - {language}"
    language_checks[sheet_name] = {
        "expected_licenses": sorted(expected),
        "actual_licenses": sorted(license_sets.get(sheet_name, set())),
        "only_passed": license_sets.get(sheet_name, set()).issubset({row["License_Number"] for row in ROWS if row["Passed_Test"] == "Yes"}),
    }

result = {
    "xlsx": str(XLSX),
    "sheet_names": [sheet["name"] for sheet in sheets],
    "first_four_columns": headers[:4],
    "column_count": len(headers),
    "master_data_rows": sheet_counts["Master"],
    "master_unique_licenses": len(license_sets["Master"]),
    "status_expected": dict(expected_status),
    "status_actual": actual_status,
    "status_reconciles": actual_status == {"Passed": expected_status["Yes"], "Failed": expected_status["No"], "Needs review": expected_status["Needs review"]},
    "language_checks": language_checks,
    "license_formula_checks": formula_checks,
}
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(result, indent=2, ensure_ascii=False))
