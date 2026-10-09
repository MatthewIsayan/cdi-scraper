"""Explain and prioritize professional licensing profiles for a Life-focused IMO.

Rules are a transparent proposed outreach rubric, not inferred probabilities or
assertions of the original reviewer's undocumented reasons.
"""
import csv
import json
import re
import html
from collections import Counter
from datetime import datetime, date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'exports'/'aguilar-review'
TODAY=date(2026,10,8)
records=json.loads((ROOT/'review-data.json').read_text(encoding='utf-8'))
HEALTH_MARKERS=['ANTHEM','BLUE SHIELD','HEALTH NET','UNITEDHEALTHCARE','HUMANA','KAISER','AETNA','WELLPOINT','CAREAMERICA','ALL SAVERS','NATIONAL HEALTH','UNIMERICA','FRESENIUS HEALTH','FIRST HEALTH','DEARBORN']
BANK_MARKERS=['CHASE INSURANCE','WELLS FARGO','EDWARD JONES','MERRILL LYNCH','MORGAN STANLEY','CHARLES SCHWAB','BANK OF AMERICA','LPL FINANCIAL']
BENEFITS_MARKERS=['GALLAGHER BENEFIT','MERCER HEALTH','MARSH & MCLENNAN','HUB INTERNATIONAL']

def names(r,key):return sorted(set(x[0]for x in r.get(key,[])if x))
def qactive(r,name):return any(q['qualification']==name and q['status']=='Active'for q in r['qualifications'])
def matches(names_,markers):return [n for n in names_ if any(p in n for p in markers)]
def parse_date(s):
    try:return datetime.strptime(s,'%m/%d/%Y').date()
    except ValueError:return None
def source(r):return f"[{r['current_name']} ({r['license_number']})]({r['url']})"
def cached_table(document, table_id):
    m=re.search(r'<table\b[^>]*\bid="'+table_id+r'"[^>]*>(.*?)</table>',document,re.S|re.I)
    if not m:return []
    return [[' '.join(html.unescape(re.sub('<[^>]*>',' ',c)).split())for c in re.findall(r'<td\b[^>]*>(.*?)(?=</td>|<td\b|</tr>)',row,re.S|re.I)]for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',m[1],re.S|re.I)if re.search('<td\\b',row,re.I)]

for r in records:
    document=(ROOT/'details'/(r['license_number']+'.html')).read_text(encoding='utf-8')
    r['sponsor_relationships']=cached_table(document,'SponsorsGrid')
    r['employer_relationships']=cached_table(document,'EmployerEmployeeGrid')
    agencies=names(r,'agencies');insurers=names(r,'appointments')
    bank=matches(agencies,BANK_MARKERS)
    confirmed=matches(insurers,['STATE FARM','FARMERS'])
    career=matches(insurers,['NEW YORK LIFE INSURANCE COMPANY','NYLIFE INSURANCE COMPANY OF ARIZONA','NORTHWESTERN MUTUAL','KNIGHTS OF COLUMBUS','THRIVENT'])+matches(agencies,['NYLIFE SECURITIES'])
    allstate=matches(insurers,['ALLSTATE '])
    benefits=matches(agencies,BENEFITS_MARKERS)
    life_insurers=sorted(set(a[0]for a in r['appointments']if a[1]=='Life'))
    core_life=[n for n in life_insurers if not any(p in n for p in HEALTH_MARKERS)]
    pc_insurers=sorted(set(a[0]for a in r['appointments']if a[1]in ['Property','Casualty','Personal Lines','Limited Lines Auto']))
    health_only=bool(r['appointments']) and not life_insurers and all(a[1]in ['Accident & Health or Sickness','Disability Only']for a in r['appointments'])
    health_skew=bool(life_insurers)and not core_life and not(r['flags']['wfg']or r['flags']['primerica'])
    pc_present=qactive(r,'Property')or qactive(r,'Casualty')or qactive(r,'Personal Lines')
    pc_skew=pc_present and not core_life and not r['flags']['wfg']
    variable=qactive(r,'Var Life and Var Annuity')
    effective_phone=r['business_phone']or(r.get('pdf_phone','')if r['approved']else '')
    contact_source='Current CDI'if r['business_phone']else('Approved PDF; current CDI omits phone'if effective_phone else'No public business phone in collected record')
    toll=effective_phone.startswith(('800','888','877','866','855','844','833'))
    lifeq=next((q for q in r['qualifications']if q['qualification']=='Life'and q['status']=='Active'),None)
    issued=parse_date(lifeq['issued'])if lifeq else None
    tenure=round((TODAY-issued).days/365.25,1)if issued else ''
    segment=('New license: training/onboarding conversation'if tenure!=''and tenure<2 else'Establishing practice: growth/carrier-access conversation'if tenure!=''and tenure<10 else'Established license: experienced broker/annuity conversation'if tenure!=''else'No active general Life authority')
    expiration=parse_date(lifeq['expires'])if lifeq else None
    expiry_days=(expiration-TODAY).days if expiration else ''
    appointment_dates=[parse_date(a[2])for a in r['appointments']if a[1]=='Life'and len(a)>2]
    appointment_dates=[d for d in appointment_dates if d]
    most_recent_life=max(appointment_dates).isoformat()if appointment_dates else ''
    orders=sorted(r.get('enforcement',[]),key=lambda a:parse_date(a[1])or date.min,reverse=True)
    order_review=bool(orders)and not any(p in orders[0][0].upper()for p in ['REMOVED','UNRESTRICTED'])
    history_removed=bool(orders)and not order_review
    signals=[];questions=[];cautions=[]
    if r['active_life']:signals.append('Active general Life authority')
    if r['flags']['wfg']:signals.append('WFG relationship: matches an explicitly targeted recruiting segment')
    if r['flags']['primerica']:signals.append('Primerica relationship: matches an explicitly targeted recruiting segment')
    if core_life:signals.append('Direct Life appointments outside the selected health-carrier set: '+', '.join(core_life))
    if not agencies and not insurers:signals.append('No agency or insurer displayed: onboarding opportunity possible; existing business unknown')
    if qactive(r,'Accident & Health or Sickness'):signals.append('Active A&H supports optional cross-selling; not necessary for target products')
    if bank:cautions.append('Bank/securities agency channel: '+', '.join(bank));questions.append('Can this person write outside their bank/broker-dealer channel?')
    if career:cautions.append('Career/member-channel signal: '+', '.join(sorted(set(career))));questions.append('Is the agency relationship portable, and is outside IMO business permitted?')
    if allstate:cautions.append('Allstate P&C appointments: verify distribution relationship; do not assume exclusivity');questions.append('Is this an exclusive agency role or an independent appointment?')
    if benefits:cautions.append('Benefits/large-broker agency signal: '+', '.join(benefits));questions.append('Does this person personally originate retail Life/final-expense/annuity cases?')
    if health_only:cautions.append('Displayed insurer appointments are A&H/disability only despite active Life authority')
    elif health_skew:cautions.append('Life appointments shown only at selected health-oriented carriers; core Life activity unestablished')
    if pc_skew:cautions.append('P&C/Personal Lines authority without displayed core Life appointments; mixed profile requires review')
    elif pc_present:cautions.append('Mixed P&C/Life qualifications; not an exclusion because approved examples have both')
    if variable:cautions.append('Variable authority: financial-advice/variable-product capability; not needed for fixed annuities and not an automatic exclusion')
    if r['sponsor_relationships']:cautions.append('Sponsor relationships displayed: '+', '.join(sorted(set(s[0]for s in r['sponsor_relationships'])))+'; inspect line-specific relationship, not a blanket employment inference')
    if toll:cautions.append('Toll-free business number: verify that it reaches the individual rather than a central office')
    if not r['flags']['ca_resident']:cautions.append('Nonresident or address state outside CA; confirm geographic recruiting scope')
    if order_review:cautions.append('Enforcement order requires direct review; latest displayed order is not a removal order');questions.append('What restrictions remain, and will the relevant carrier approve contracting?')
    elif history_removed:cautions.append('Historical enforcement with later removal/unrestricted wording; not treated as a current restriction')
    if expiry_days!=''and expiry_days<=60:cautions.append(f'Life expiration in {expiry_days} days: confirm renewal during onboarding')
    if not effective_phone:cautions.append('No public business phone: contact enrichment needed, not proof of poor recruiting fit')
    elif not r['business_phone']:cautions.append('Approved PDF has a phone that current CDI does not display; verify currency')
    if not core_life and not r['flags']['wfg']and not r['flags']['primerica']:questions.append('Is this person actively writing Life/final expense/IUL/fixed annuities or merely holding the license?')
    if r['active_life']:questions.append('What business do they write, who controls contracts, and what would the IMO add?')

    if not r['active_life']:
        tier=7;route='Outside current general-Life recruiting pool';reason='No active general Life qualification; inactive or other/limited authority is a licensing mismatch.';confidence='Observed qualification'
    elif confirmed:
        tier=6;route='Exclude under confirmed company rule';reason='State Farm/Farmers appointment: applies the user-confirmed exclusion.';confidence='User-confirmed rule'
    elif not effective_phone:
        tier=5;route='Find contact information first';reason='Active Life but no public business phone; assess product/channel signals after finding contact.';confidence='Observed contact gap; fit varies'
    elif not r['flags']['ca_resident']:
        tier=4;route='Geographic scope review';reason='Outside CA-resident baseline; retain actual prior approval and confirm scope.';confidence='Strong geographic pattern, known approved exception'
    elif order_review:
        tier=3;route='Review order and contracting';reason='Review actual enforcement terms before prioritizing contracting; prior approval is retained.';confidence='Observed order, effect requires verification'
    elif bank or career or allstate or benefits:
        tier=3;route='Verify distribution channel';reason='Named agency/carrier relationship suggests a different or potentially constrained distribution route: '+', '.join(sorted(set(bank+career+allstate+benefits)))+'.';confidence='Channel hypothesis; not a proven contract limitation'
    elif health_only or health_skew or pc_skew or toll:
        tier=2;route='Secondary call: verify product focus/reachability';reason='; '.join(c for c in cautions if any(p in c for p in ['A&H/disability','health-oriented','without displayed core','Toll-free']))+'.';confidence='Observable profile; weak-to-moderate omission explanation'
    else:
        tier=1;route='First-call fit for stated IMO focus';reason='Active Life, reachable, CA-resident baseline, without the specified channel/product impediments. '+('WFG/Primerica segment match.'if r['flags']['wfg']or r['flags']['primerica']else'Direct Life portfolio supports product alignment.'if core_life else'No displayed affiliation; ask about current activity.');confidence='Proposed fit; not evidence of willingness or production'
    r.update({'priority_tier':tier,'proposed_route':route,'main_reason':reason,'reason_confidence':confidence,'effective_business_phone':effective_phone,'phone_source':contact_source,'life_tenure_years':tenure,'experience_segment':segment,'life_expiration_days':expiry_days,'most_recent_life_insurer_appointment':most_recent_life,'core_life_appointment_carriers':' | '.join(core_life),'pc_appointment_carriers':' | '.join(pc_insurers),'positive_signals':' | '.join(signals),'review_flags':' | '.join(cautions),'first_call_questions':' | '.join(dict.fromkeys(questions)), 'bank_signal':bool(bank),'career_signal':bool(career),'health_only_appointments':health_only,'health_skew':health_skew,'pc_skew':pc_skew,'order_review':order_review,'variable_authority':variable,'benefits_agency_signal':bool(benefits),'sponsor_signal':bool(r['sponsor_relationships'])})

FIELDS=['priority_tier','proposed_route','approved','current_name','license_number','effective_business_phone','phone_source','main_reason','reason_confidence','positive_signals','review_flags','first_call_questions','life_tenure_years','experience_segment','life_expiration_days','most_recent_life_insurer_appointment','languages','business_address','residency','core_life_appointment_carriers','pc_appointment_carriers','agencies','appointments','sponsor_relationships','employer_relationships','qualifications','enforcement','complaints','url']
def write(name,rows):
    with (ROOT/name).open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
        for r in sorted(rows,key=lambda e:(e['priority_tier'],e['current_name'],e['license_number'])):
            row={k:r.get(k,'')for k in FIELDS}
            for k in ['agencies','appointments','enforcement','sponsor_relationships','employer_relationships','complaints']:row[k]=' | '.join(' / '.join(a)for a in r[k])
            row['qualifications']=' | '.join('; '.join(f'{k}: {v}'for k,v in q.items())for q in r['qualifications'])
            for k,v in row.items():
                if isinstance(v,str)and v.startswith(('=','+','-','@')):row[k]="'"+v
            w.writerow(row)
active=[r for r in records if r['active_life']]
new_first=[r for r in active if not r['approved']and r['priority_tier']==1]
write('refined-active-life-list.csv',active)
write('proposed-additions-first-call.csv',new_first)
write('refined-all-producers.csv',records)
(ROOT/'refined-data.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
tiers={t:{'route':'Channel or contracting verification'if t==3 else next(r['proposed_route']for r in records if r['priority_tier']==t),'approved':sum(r['approved']and r['priority_tier']==t for r in records),'not_approved':sum(not r['approved']and r['priority_tier']==t for r in records)}for t in sorted(set(r['priority_tier']for r in records))}
factors=['bank_signal','career_signal','benefits_agency_signal','health_only_appointments','health_skew','pc_skew','order_review','variable_authority','sponsor_signal']
factor_counts={f:{'approved':sum(r[f]for r in active if r['approved']),'not_approved_active_life':sum(r[f]for r in active if not r['approved'])}for f in factors}
summary={'focus':'Life, final expense, IUL, fixed annuities','tiers':tiers,'factor_counts':factor_counts,'proposed_first_call_additions':len(new_first),'first_call_previously_approved':sum(r['approved']and r['priority_tier']==1 for r in active)}
(ROOT/'refined-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
lines=['# Refined IMO recruiting analysis','', 'Focus: Life, final expense, IUL, and fixed annuities. Uses the public records checked October 8, 2026 and the original 136 approved licenses. Existing approval labels are retained. Proposed routes are an outreach rubric, not a prediction of the father\'s exact historical motive or a carrier-contracting decision.','', '## Routing results','', '| Proposed route | Previously approved | Not previously approved |','|---|---:|---:|']
for t,v in tiers.items():lines.append(f"| {t}. {v['route']} | {v['approved']} | {v['not_approved']} |")
lines+=['','Routing is sequential: license mismatch, confirmed company exclusion, contact gap, geography, orders, other channels, product-focus review, first-call fit. Every row still retains all applicable factors. Missing phones and nonresident records are operational holds, not evidence that a person is a poor producer.','', '## Additional explanatory factors','', '| Factor | Approved | Omitted active-Life |','|---|---:|---:|']
for f,v in factor_counts.items():lines.append(f"| {f.replace('_',' ')} | {v['approved']} | {v['not_approved_active_life']} |")
lines+=['','## Interpretation and evidence strength','', '- **Confirmed exclusions:** State Farm/Farmers, as confirmed by the user. No active general Life authority is a qualification mismatch for this specific pool.', '- **Strong observed tendencies:** contact availability, California residency, and bank/securities channels. Bank endorsement is more informative than an annuity carrier name alone.', '- **Additional channel review:** New York Life career-associated combinations, NYLIFE Securities, Northwestern Mutual, Knights of Columbus, and Thrivent. These are hypotheses about distribution fit, not proof of exclusivity. Allstate P&C and large benefits-broker relationships need verification as well.', '- **Product focus:** only A&H/disability insurer appointments despite an active Life license are a useful mismatch signal. Health-carrier-heavy and P&C-heavy combinations can lower outreach priority, especially without separate core Life relationships. Qualification and appointment rows do not prove actual product sales.', '- **Positive Life evidence:** WFG/Primerica relationships and direct Life appointments outside a explicitly listed health-carrier set. The set is an interpretable heuristic, not an exhaustive carrier-product classification.', '- **Variable authority:** only 4 approved versus 31 omitted active-Life producers have it. It often co-occurs with bank/financial-advice channels. Fixed annuities do not require treating variable authority as a positive recruiting prerequisite; it is not an exclusion.', '- **Tenure:** the reachable CA-Life cohort has median Life qualification tenure of 2.5 years among approved and 7.0 among omitted. New-license candidates fit training/onboarding; experienced candidates fit growth, carrier-access, and annuity discussions. No age or production level is inferred, and no tenure cutoff is used.', '- **Licensing orders:** one approved producer also has a restriction-related order. Review actual orders rather than inventing a universal historical-discipline exclusion. Removal orders are distinguished from restriction orders without subsequent removal wording.', '- **Expiry:** a renewal reminder, not an exclusion. The remaining days refer to the Life qualification.', '- **Contact quality:** toll-free numbers may be central lines; verify direct reachability. Shared business phones are common in the approved list, so shared numbers are not penalized.', '- **Languages:** retained as reported for outreach planning. No ethnicity or language is inferred from names and no language ranking is applied without a stated business need.', '- **Do not blacklist a carrier from a zero-approved count:** Pacific Life, Equitable, and New York Life also distribute through third parties; surrounding agencies and appointment mix matter. AAA, Guardian, P&C credentials, and historical restrictions have approved exceptions.','', '## Proposed first-call additions','',f'{len(new_first)} omitted producers meet the proposed first-call profile. They remain NOT previously approved. Their omission is not explained by the specified observed impediments.','']
for r in sorted(new_first,key=lambda r:r['current_name']):lines.append(f"- {source(r)} — {r['main_reason']} Segment: {r['experience_segment']}." )
lines+=['','## Person-specific examples','']
for lic in ['0J17106','4414588','0M16581','0M67579','0L87403','0F57818','0J10393','0M62601','4526717','4575418','4409571','4357005']:
    r=next(r for r in records if r['license_number']==lic)
    lines +=[f"- **{source(r)}** — {'Approved'if r['approved']else'Omitted'}; proposed route: {r['proposed_route']}. {r['main_reason']} Flags: {r['review_flags']or'none under this rubric'}." ]
lines+=['','## Sources and limits','', '- [CDI Check a License](https://www.insurance.ca.gov/0200-industry/0008-check-license-status/): qualifications and discipline lookup.', '- [New York Life career paths](https://www.newyorklife.com/careers/financial-professionals/career-paths): career agents and NYLIFE Securities.', '- [New York Life third-party Life distribution](https://www.newyorklife.com/amn/retail-life): a carrier appointment alone does not prove career-channel exclusivity.', '- [Northwestern Mutual careers](https://www.northwesternmutual.com/careers/): financial-representative channel.', '- [Knights of Columbus insurance-agent careers](https://www.kofc.org/career/insurance-agent-careers/): field-agent channel.', '- [Thrivent career options](https://careers.thrivent.com/financial-professional-careers/): multiple practice pathways; do not presume exclusivity.', '- [Allstate agency FAQs](https://www.allstate.com/lps/startanagency/faqs): exclusive agency roles exist; verify the person\'s actual role.', '', 'The record-specific CDI URLs and raw appointment/qualification facts are included in every exported row. No public license page proves production volume, book ownership, compensation, contract-release rules, current employment, IUL/final-expense specialization, carrier willingness to appoint, or interest in moving. These are first-call questions, not inferred personal attributes.','']
(ROOT/'refined-analysis.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(summary,indent=2))
