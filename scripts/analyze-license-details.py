"""Summarize cached public CDI records; retain extracted facts for review."""
import html
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'exports' / 'license-details-cache'


def text(fragment):
    fragment = re.sub(r'<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>', '', fragment, flags=re.S | re.I)
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ', fragment)).split())


def table_rows(document, table_id):
    match = re.search(r'<table\b[^>]*\bid="' + re.escape(table_id) + r'"[^>]*>(.*?)</table>', document, re.S | re.I)
    if not match:
        return []
    return [
        [text(cell) for cell in re.findall(r'<td\b[^>]*>(.*?)(?=</td>|<td\b|</tr>)', row, re.S | re.I)]
        for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', match.group(1), re.S | re.I)
        if re.search(r'<td\b', row, re.I)
    ]


def analyze(row):
    path = CACHE / (row['license_number'] + '.html')
    if not path.exists():
        failed = (CACHE / (row['license_number'] + '.error.txt')).exists()
        return {'agent_analysis': 'Licensing page unavailable. Details could not be verified.' if failed else 'Licensing review pending.', 'license_checked_on': '', 'lookup_status': 'unavailable' if failed else 'pending'}
    doc = path.read_text(encoding='utf-8-sig')
    lic = row['license_number']
    if not re.search(r'License #:\s*' + re.escape(lic) + r'\s*<', doc):
        raise ValueError(f'License identity mismatch: {lic}')
    qualifications = table_rows(doc, 'licenseDetailGrid')
    if not qualifications or any(len(q) != 5 for q in qualifications):
        raise ValueError(f'Unexpected license table: {lic} {qualifications}')
    facts = [dict(zip(['qualification', 'issued', 'status', 'status_date', 'expires'], q)) for q in qualifications]
    statements = []
    statuses = list(dict.fromkeys(q['status'] for q in facts))
    for status in statuses:
        types = [q['qualification'].replace('Accident & Health or Sickness', 'Accident & Health') for q in facts if q['status'] == status]
        statements.append(f'{status} licenses: {", ".join(types)}.')
    issue_dates = [datetime.strptime(q['issued'], '%m/%d/%Y') for q in facts if q['issued']]
    if issue_dates:
        statements.append(f'First issued {min(issue_dates):%m/%d/%Y}.')
    active_expirations = list(dict.fromkeys(q['expires'] for q in facts if q['status'].lower() == 'active' and q['expires']))
    if active_expirations:
        statements.append('Active license expiration: ' + ', '.join(active_expirations) + '.')
    languages_match = re.search(r'<b>\s*Language:\s*</b>(.*?)</div>', doc, re.S | re.I)
    languages = ', '.join(dict.fromkeys(part.strip() for part in text(languages_match.group(1)).split(',') if part.strip())) if languages_match else ''
    if languages:
        statements.append(f'Languages: {languages}.')
    appointments = table_rows(doc, 'AppointmentGrid')
    insurer_names = list(dict.fromkeys(q[0] for q in appointments if q and q[0]))
    if insurer_names:
        statements.append(f'{len(insurer_names)} insurer appointment' + ('s' if len(insurer_names) != 1 else '') + ' listed.')
    complaints = table_rows(doc, 'ConsumerComplaintGrid')
    if complaints:
        statements.append('Justified complaints shown: ' + ', '.join(f'{q[1]} in {q[0]}' for q in complaints) + '.')
    headings = list(re.finditer(r'<h3\b[^>]*>(.*?)</h3>', doc, re.S | re.I))
    enforcement = []
    section_names = []
    for index, heading in enumerate(headings):
        name = text(heading.group(1))
        section_names.append(name)
        if re.search(r'enforcement|disciplin|order|restriction', name, re.I):
            end = headings[index + 1].start() if index + 1 < len(headings) else doc.find('<footer', heading.end())
            if end < 0:
                end = len(doc)
            detail = text(doc[heading.end():end])
            enforcement.append({'section': name, 'detail': detail})
    enforcement_rows = table_rows(doc, 'EnforcementActionGrid')
    if enforcement_rows:
        latest = max(enforcement_rows, key=lambda q: datetime.strptime(q[1], '%m/%d/%Y'))
        latest_description = latest[0].upper()
        if 'RESTRICTIONS' in latest_description and 'REMOVED' in latest_description:
            historical_type = 'revocation/restricted-license orders' if any('REVOKED' in q[0].upper() for q in enforcement_rows) else 'restricted-license orders'
            statements.append(f'Historical {historical_type} listed. Restrictions removed {latest[1]}.')
        elif 'WARNING LETTER SENT' in latest_description:
            statements.append(f'Enforcement: warning letter dated {latest[1]}.')
        elif lic == '0F95336' and 'BANNED' in latest_description and 'FEBRUARY 16, 2023' in latest_description:
            statements.append('Enforcement: industry ban 10/21/2022 through 02/16/2023, followed by a restricted-license order.')
        elif 'ISSUE IN LIEU THEREOF A RESTRICTED LICENSE' in latest_description:
            statements.append(f'Enforcement: restricted-license order dated {latest[1]}.')
        else:
            statements.append(f'Enforcement orders displayed, latest dated {latest[1]}. Review the licensing page.')
    elif enforcement:
        statements.append('Enforcement information displayed. Review the licensing page for details.')
    else:
        statements.append('No enforcement action displayed.')
    checked = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d')
    return {
        'agent_analysis': ' '.join(statements),
        'license_checked_on': checked,
        'lookup_status': 'verified',
        'facts': {'qualifications': facts, 'languages': languages, 'insurers': insurer_names, 'complaints': complaints, 'enforcement': enforcement, 'enforcement_rows': enforcement_rows, 'sections': section_names},
    }


rows = json.loads((CACHE / 'source-rows.json').read_text(encoding='utf-8-sig'))
results = [{'license_number': row['license_number'], **analyze(row)} for row in rows]
(CACHE / 'analysis.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'total': len(results), 'statuses': dict(Counter(r['lookup_status'] for r in results)), 'complaints_displayed': sum(bool(r.get('facts', {}).get('complaints')) for r in results), 'enforcement_displayed': sum(bool(r.get('facts', {}).get('enforcement')) for r in results)}, indent=2))
for row, result in list(zip(rows, results))[:2]:
    print(row['name'] + ': ' + result['agent_analysis'])
