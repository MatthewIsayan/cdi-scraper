"""Compare the prior delivered test workbook decisions with the rerun."""
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "outputs/test-batch-50/cdi-agents-test-batch-50.xlsx"
CURRENT = json.loads((ROOT / "exports/test-batch-50/selected-rows.json").read_text(encoding="utf-8"))
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

with zipfile.ZipFile(XLSX) as zf:
    root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    previous = {}
    for row in root.findall(".//x:sheetData/x:row", NS)[1:]:
        cells = {"".join(ch for ch in cell.attrib.get("r", "") if ch.isalpha()): (cell.find("x:v", NS).text if cell.find("x:v", NS) is not None else "") for cell in row.findall("x:c", NS)}
        if cells.get("E"):
            previous[cells["E"]] = cells.get("B", "") or "REVIEW"

current = {row["License_Number"]: (row["Passed_Test"] or "REVIEW") for row in CURRENT}
changes = [{"license_number": license_number, "previous": previous.get(license_number, "MISSING"), "current": current.get(license_number, "MISSING")} for license_number in sorted(set(previous) | set(current)) if previous.get(license_number, "MISSING") != current.get(license_number, "MISSING")]
result = {"previous_count": len(previous), "current_count": len(current), "decision_changes": changes, "decisions_changed": bool(changes)}
(ROOT / "exports/test-batch-50/decision-change-audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
