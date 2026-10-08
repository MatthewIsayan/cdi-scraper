"""Produce auditable selection-pattern reports from verified public facts."""
import csv
import json
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]/'exports'/'aguilar-review'
records=json.loads((ROOT/'comparison.json').read_text(encoding='utf-8'))

def names(r,key):return sorted(set(x[0] for x in r.get(key,[]) if x))
def flags(r):
    agencies=names(r,'agencies');insurers=names(r,'appointments')
    both=agencies+insurers
    return {
        'active_life':r.get('active_life',False),
        'phone_displayed':bool(r.get('business_phone')),
        'ca_resident':r.get('residency')=='Resident' and r.get('search_state')=='CA',
        'wfg':any('WORLD FINANCIAL GROUP' in s for s in both),
        'primerica':any('PRIMERICA' in s for s in both),
        'state_farm_or_farmers':any('STATE FARM' in s or 'FARMERS' in s for s in insurers),
        'bank_or_securities_agency':any(any(p in s for p in ['CHASE INSURANCE','WELLS FARGO','EDWARD JONES','MORGAN STANLEY','MERRILL LYNCH','CHARLES SCHWAB','BANK OF AMERICA']) for s in agencies),
        'active_property_or_casualty':any(q.get('qualification') in ['Property','Casualty'] and q.get('status')=='Active' for q in r.get('qualifications',[])),
        'no_agency_or_insurer_displayed':not both,
    }

for r in records:
    r['flags']=flags(r)
    r['list_membership']='Approved in supplied PDF' if r['approved'] else 'Not approved: absent from supplied PDF'
    f=r['flags'];facts=[]
    if 'error' in r:r['interpretation']='Unverified licensing detail: '+r['error'];continue
    facts.append('Active Life authority' if f['active_life'] else 'No active Life authority displayed')
    facts.append('Business phone displayed' if f['phone_displayed'] else 'No business phone displayed')
    if not f['ca_resident']:facts.append('Nonresident or address state outside California')
    if f['wfg']:facts.append('WFG affiliation displayed')
    if f['primerica']:facts.append('Primerica affiliation displayed')
    if f['state_farm_or_farmers']:facts.append('State Farm or Farmers insurer appointment displayed')
    if f['bank_or_securities_agency']:facts.append('Bank or securities distribution agency displayed')
    if f['active_property_or_casualty']:facts.append('Active Property/Casualty authority also displayed')
    if f['no_agency_or_insurer_displayed']:facts.append('No agency/insurer affiliation displayed; independence not established')
    r['interpretation']='; '.join(facts)+'. '
    if r['approved']:r['interpretation']+='Selection is confirmed by PDF membership; public facts do not establish the father\'s motive.'
    elif not f['active_life']:r['interpretation']+='Lack of active Life authority is a plausible omission explanation.'
    elif not f['ca_resident']:r['interpretation']+='Geographic mismatch is a plausible omission explanation, with an approved exception.'
    elif not f['phone_displayed']:r['interpretation']+='Lack of a listed phone may explain omission from a calling list; this is a current snapshot.'
    elif f['state_farm_or_farmers'] or f['bank_or_securities_agency']:r['interpretation']+='Affiliation may indicate a different distribution channel; exclusivity and willingness to move are not established.'
    elif f['active_property_or_casualty']:r['interpretation']+='Mixed Life/P&C profile may explain omission, but approved P&C exceptions prevent a firm rule.'
    else:r['interpretation']+='Meets the active-Life/California-resident/phone baseline; omission remains unexplained by these filters.'

fields=['list_membership','license_number','current_name','search_names','residency','search_city','search_state','search_status','active_life','business_phone','business_address','pdf_group','pdf_phone','qualifications','agencies','appointments','enforcement','interpretation','url']
def write_csv(name,rows):
    with (ROOT/name).open('w',encoding='utf-8-sig',newline='')as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader()
        for r in sorted(rows,key=lambda e:(e.get('current_name',''),e['license_number'])):
            row={k:r.get(k,'')for k in fields}
            row['search_names']=' | '.join(r['search_names'])
            row['qualifications']=' | '.join('; '.join(f'{k}: {v}' for k,v in q.items())for q in r.get('qualifications',[]))
            for k in ['agencies','appointments','enforcement']:row[k]=' | '.join(' / '.join(x)for x in r.get(k,[]))
            for k,v in row.items():
                if isinstance(v,str) and v.startswith(('=','+','-','@')):row[k]="'"+v
            w.writerow(row)

approved=[r for r in records if r['approved']]
unlisted=[r for r in records if not r['approved']]
active_unlisted=[r for r in unlisted if r.get('active_life')]
baseline_unlisted=[r for r in active_unlisted if r['flags']['ca_resident'] and r['flags']['phone_displayed']]
exceptions=[r for r in baseline_unlisted if not any(r['flags'][k]for k in ['state_farm_or_farmers','bank_or_securities_agency','active_property_or_casualty'])]
for name,rows in [('all-producers.csv',records),('approved-producers.csv',approved),('not-approved-producers.csv',unlisted),('unexplained-omissions.csv',exceptions)]:write_csv(name,rows)
(ROOT/'review-data.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
metrics={k:{'approved':sum(r['flags'][k]for r in approved),'not_approved':sum(r['flags'][k]for r in unlisted),'not_approved_active_life':sum(r['flags'][k]for r in active_unlisted)}for k in flags(records[0])}
summary={'total':len(records),'approved':len(approved),'not_approved':len(unlisted),'not_approved_active_life':len(active_unlisted),'baseline_unlisted':len(baseline_unlisted),'exceptions':len(exceptions),'unverified':sum('error'in r for r in records),'metrics':metrics,'approved_pdf_groups':dict(Counter(r.get('pdf_group','')for r in approved))}
(ROOT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

def link(r):return f"[{r.get('current_name') or r.get('name') or r['license_number']} — {r['license_number']}]({r['url']})"
lines=['# Aguilar producer selection comparison','', 'Public CDI records checked October 8, 2026. Approval means membership in the supplied detailed PDF; absence means not approved under the user\'s instruction. The PDFs were created October 5. Current records cannot establish a historical motive or guarantee that every omitted person was reviewed.','',f"The A–Z first-name searches for surname Aguilar returned 2,035 rows, deduplicated into {len(records):,} licenses. All 136 approved licenses were found. Historical names and compound surnames are included when returned by CDI. A–Z subdivision was necessary because the surname-only query exceeded the site\'s 500-record limit.",'',f"- Approved: **{len(approved)}**",f"- Not approved under supplied-list membership: **{len(unlisted):,}**",f"- Not approved with active Life authority: **{len(active_unlisted)}**",f"- Unverified detail records: **{summary['unverified']}**",'', '## Observed facts','', '| Public-record characteristic | Approved (136) | Not approved, active Life only |','|---|---:|---:|']
labels={'active_life':'Active Life authority','phone_displayed':'Business phone displayed','ca_resident':'California resident and CA search address','wfg':'WFG agency/insurer name displayed','primerica':'Primerica agency/insurer name displayed','state_farm_or_farmers':'State Farm/Farmers insurer name displayed','bank_or_securities_agency':'Selected bank/securities agency names displayed','active_property_or_casualty':'Active Property/Casualty authority','no_agency_or_insurer_displayed':'No agency/insurer affiliation displayed'}
for k,label in labels.items():lines.append(f"| {label} | {metrics[k]['approved']} | {metrics[k]['not_approved_active_life']} |")
lines+=['','Counts overlap. Active Life means the CDI qualification named Life; funeral/burial-limited authority alone is not included in that count. Agency names and insurer appointments are distinct public facts. An appointment is not proof of employment, exclusivity, production volume, contract portability, or willingness to change agencies. Missing appointments do not prove that a person is independent.','', '## Best-supported interpretation','', 'The supplied list strongly favors active Life producers reachable by business phone, overwhelmingly in California. WFG and Primerica were explicit recruiting segments. The comparison can support a preference for Life distribution channels over State Farm/Farmers and bank channels, but it does not prove an exclusive-carrier rule. Active Property/Casualty authority cannot be an absolute exclusion: approved people have it too.','',f"There are **{len(baseline_unlisted)}** unlisted active-Life producers with a California-resident record and a public business phone. Of these, **{len(exceptions)}** also lack the particular bank, State Farm/Farmers, and active P&C flags used here. These are counterexamples to a simple mechanical rule; they are not new recruitment recommendations.",'', '## Concrete approved examples','']
for lic in ['0N06406','4441723','0M62601','0G01763']:
    r=next((r for r in approved if r['license_number']==lic),None)
    if r:lines += [f"- {link(r)}: {r['interpretation']} Agencies: {', '.join(names(r,'agencies')) or 'none displayed'}. Insurers: {', '.join(names(r,'appointments')) or 'none displayed'}."]
lines+=['','## Concrete unlisted examples','']
for lic in ['0J17106','0E37291','4414588','0K79449','4443915']:
    r=next((r for r in unlisted if r['license_number']==lic),None)
    if r:lines +=[f"- {link(r)}: {r['interpretation']} Agencies: {', '.join(names(r,'agencies')) or 'none displayed'}. Insurers: {', '.join(names(r,'appointments')) or 'none displayed'}."]
lines+=['','## Omitted WFG/Primerica examples that meet the baseline','']
for r in [r for r in baseline_unlisted if r['flags']['wfg']or r['flags']['primerica']]:lines +=[f"- {link(r)}: {r['interpretation']}"]
lines+=['','## Approved exceptions to proposed filters','']
for r in approved:
    if not r['flags']['ca_resident'] or not r['flags']['phone_displayed'] or r['flags']['active_property_or_casualty']:
        lines +=[f"- {link(r)}: {r['interpretation']}"]
lines+=['','## Files and source traceability','', '- `approved-producers.csv`: every approved producer, exact current source URL, qualifications, agencies, insurers, and factual interpretation.', '- `not-approved-producers.csv`: every unlisted license in the A–Z results, same evidence fields.', '- `all-producers.csv`: complete comparison.', '- `unexplained-omissions.csv`: unlisted baseline matches without the selected distribution/P&C flags.', '- `search-rows.json`: original search rows and per-initial result counts.', '- `details/`: cached HTML for the source pages, each identity-checked against its license number.', '', 'The detailed supplied PDF has 136 unique licenses: 7 explicitly marked WFG, 33 explicitly marked Primerica, and 96 marked affiliation unidentified in source. Those original labels are retained separately from current CDI affiliations. Their counts need not equal current WFG/Primerica counts.','', 'Search source: https://cdicloud.insurance.ca.gov/cal/IndividualNameSearch','']
(ROOT/'analysis.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(summary,indent=2))
