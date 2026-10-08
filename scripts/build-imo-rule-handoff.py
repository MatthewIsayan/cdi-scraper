"""Small reviewer handoff: positive controls and user-authorized working rules."""
import json
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'exports/aguilar-review/refined-data.json').read_text())
approved=[r for r in rows if r['approved']]
carriers=Counter(n for r in approved for n in {x[0] for x in r['appointments'] if x[1]=='Life'})
agencies=Counter(n for r in approved for n in {x[0] for x in r['agencies']})
intro='''# Recruiting rules: our current understanding

Please correct the rules below where needed. We have used approved examples
to establish acceptable profiles and strong omission patterns to establish
working exclusions. We are not asking you to review individual people.

## Profiles we keep

| Accepted profile | Why we keep it |
|---|---|
| WFG producers | An established approved recruiting audience; existing organization membership is not itself a reason to reject. |
| Primerica producers | Another approved recruiting audience; do not require the person to be unaffiliated. |
| New York Life / NYLIFE and Northwestern Mutual | Explicitly confirmed acceptable by the user. No general career-profile exclusion applies. |
| Producers with other Life insurer appointments | Existing Life relationships are relevant to the IMO offer; no single required carrier. |
| No displayed agency or appointments | 25 approved examples: the IMO can recruit people who need contracting/onboarding. No listed affiliation does not prove independence. |
| New license holders | 60 approved have Life issue dates less than two years before the check. Training prospects are acceptable. |
| Experienced license holders | 23 approved have Life issue dates ten or more years before the check. We can offer carrier access and support; no tenure cap. |
| Life plus auto/home qualifications | Six approved have active P&C authority. Other lines do not erase the Life recruiting opportunity. |
| Life plus variable authority | Four approved have it. Additional qualifications do not disqualify someone from this fixed-product recruiting pool. |
| Health relationships alongside Life | Approved examples have health insurer and exchange relationships; do not automatically reject health involvement. |
| Large or multi-line agencies | AssuredPartners, Acrisure, Filice and IMA appear in approved records. Company size or benefits involvement alone is not a rejection rule. |
| Life-agency focus | Seek Life agencies and Life-business relationships. Auto/home involvement is not a target signal, but does not automatically disqualify an otherwise suitable Life prospect. |
| AAA Life, Guardian and Foremost relationships | Approved examples prevent blanket rejection of these exact relationships. Keep insurer entities distinct. |
| One insurer or several insurers | No required carrier count has been established; do not infer production or exclusivity from count. |
| Missing business contact | Save an otherwise suitable lead for contact research; do not reject it. |
| Direct individual business contact | Required for outreach readiness. Shared-office or toll-free-only numbers require direct-contact research; earlier inclusions may have been accidental. |

These are accepted features, not guarantees that every person with one of them
passes. A separate exclusion may still apply. Carrier appointments do not prove
current product sales or freedom to change contracts.

## Exclusions and how we apply them

| Rule | Working result | Basis |
|---|---|---|
| Current State Farm/Farmers relationship | Exclude | User-confirmed rule; 17 omitted active-Life records, none approved. |
| Current bank/securities agency relationship | Exclude from the main recruiting list, including other verified bank/securities agencies | User-confirmed general rule; 20 omitted, none approved in the cached comparison. Applies to the agency relationship, not an annuity insurer name or variable authority alone. |
| Current Allstate, Knights of Columbus or Thrivent relationship | Exclude | Explicit user confirmation. New York Life / NYLIFE and Northwestern Mutual are acceptable; no general career-profile exclusion. |
| Other large or benefits agency | Do not reject as a whole category | Approved large/multi-line agencies contradict that blanket rule. Specific agency exceptions can be added below. |
| Mixed Life, health, auto/home, or variable qualifications | Do not reject for the mix alone | Approved examples exist. |

Bank/securities agency entries actually observed in the omitted group:
- CHASE INSURANCE AGENCY, INC. — 11
- WELLS FARGO WEALTH BROKERAGE INSURANCE AGENCY LLC — 5
- EDWARD JONES INSURANCE AGENCY OF CALIFORNIA, LLC — 2
- MERRILL LYNCH LIFE AGENCY, INC. — 2
- LPL FINANCIAL LLC — 1

Counts overlap: these are 20 unique producers. This exclusion describes our
chosen audience; it does not prove the person is legally unable to join an IMO.
An acceptable Life insurer appointment does not cancel the bank-agency rule
under the user-confirmed rule.

## Only corrections we still need

**Specific benefits-agency exceptions.** We keep large/multi-line agencies
because approved examples exist. Gallagher Benefit Services, Mercer Health,
Marsh & McLennan, and HUB had six omitted profiles and none approved within
the selected marker set. Are these specific agencies intentional exceptions
to the accepted-agency rule, or should they remain eligible too?

Latest comparison: Gallagher acquired accepted AssuredPartners. Mercer and
Marsh share a corporate family; HUB overlaps accepted large brokers in business
scope. No broad benefits-broker exclusion is established. Health/P&C-only
displayed relationships also have approved counterexamples; see
`docs/imo-rule-boundary-evidence.md`. Absence of displayed Life relationships
does not prove absence of policy production.

Do not ask about obvious licensing prerequisites, geography, actual product
sales, discipline, or generic additional criteria in this handoff.

## Accepted relationships in the approved records

The following is an evidence list: these exact relationships appeared on
approved producers' October 8, 2026 records. It is not an automatic carrier
whitelist. Other relationships on the same person's page can still matter.
Counts are unique approved licenses and overlap. Organizations are historical
evidence, not a preferred target list; auto/home agencies are not the target.

### Agencies and organizations

| Exact listed organization | Approved producers |
|---|---:|
'''
lines=[intro]
lines.extend(f'| {n} | {c} |\n' for n,c in agencies.most_common())
lines.append('\n### Insurer appointments listed for Life\n\n| Exact listed insurer | Approved producers |\n|---|---:|\n')
lines.extend(f'| {n} | {c} |\n' for n,c in carriers.most_common())
(root/'docs/imo-approval-understanding.md').write_text(''.join(lines),encoding='utf-8')
print('Created reviewer handoff:',len(agencies),'approved organization names;',len(carriers),'approved Life insurer names.')
