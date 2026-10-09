"""Extract structured facts from the persisted test-batch CDI pages."""
import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--cache", default="test-batch-50")
args = parser.parse_args()
cache = ROOT / "exports" / args.cache


def clean(value):
    value = re.sub(r"<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>", "", value, flags=re.S | re.I)
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", value)).split())


def table_rows(document, table_id):
    match = re.search(r'<table\b[^>]*\bid=["\']' + re.escape(table_id) + r'["\'][^>]*>(.*?)</table>', document, re.S | re.I)
    if not match:
        return []
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


manifest = json.loads((cache / "source-rows.json").read_text(encoding="utf-8-sig"))
results = []
for entry in manifest:
    row = entry["input"]
    license_number = row["license_number"]
    entry = dict(entry)
    path = cache / f"{license_number}.html"
    if entry.get("error") or not path.exists():
        entry["facts"] = {}
        results.append(entry)
        continue
    document = path.read_text(encoding="utf-8-sig")
    if not re.search(r"License #:\s*" + re.escape(license_number) + r"\s*<", document):
        entry["error"] = "license identity mismatch in cached document"
        entry["facts"] = {}
        results.append(entry)
        continue
    qualifications = table_rows(document, "licenseDetailGrid")
    entry["facts"] = {
        "name": next((clean(x) for x in re.findall(r"<h3\b[^>]*>(.*?)</h3>", document, re.S | re.I) if "Name:" in clean(x)), ""),
        "qualifications": qualifications,
        "appointments": table_rows(document, "AppointmentGrid"),
        "agencies": table_rows(document, "EndorsingOrganizationsGrid"),
        "orders": table_rows(document, "EnforcementActionGrid"),
        "complaints": table_rows(document, "ConsumerComplaintGrid"),
        "business_address": labeled_value(document, "Business Address:"),
        "business_phone": labeled_value(document, "Business Phone:"),
        "languages": labeled_value(document, "Language:"),
    }
    results.append(entry)

(cache / "facts.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({
    "records": len(results),
    "extraction_errors": sum(bool(x.get("error")) for x in results),
    "missing_qualification_tables": sum(not x.get("facts", {}).get("qualifications") for x in results if not x.get("error")),
    "agencies": sorted({r[0] for e in results for r in e.get("facts", {}).get("agencies", []) if r}),
}, indent=2, ensure_ascii=False))
