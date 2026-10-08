from pathlib import Path
from html import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf'
OUT.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
styles = getSampleStyleSheet()
for name, font, size, leading, after in [
    ('BodyClean', 'Arial', 10, 13, 8),
    ('SmallClean', 'Arial', 8.5, 11, 6),
    ('TitleClean', 'Arial-Bold', 21, 25, 10),
    ('H1Clean', 'Arial-Bold', 15, 19, 9),
    ('H2Clean', 'Arial-Bold', 11, 14, 6),
    ('CellClean', 'Arial', 9, 11.5, 0),
    ('HeadClean', 'Arial-Bold', 9, 11.5, 0),
]:
    styles.add(ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, spaceAfter=after,
        textColor=colors.white if name == 'HeadClean' else colors.black))
flow = []

def p(text, style='BodyClean'):
    flow.append(Paragraph(text, styles[style]))

def table(headers, rows, widths):
    data = [[Paragraph(escape(x), styles['HeadClean']) for x in headers]]
    data.extend([[Paragraph(escape(str(x)), styles['CellClean']) for x in row] for row in rows])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#243B53')),
        ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#D9D9D9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F4F6F8')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    flow.extend([t, Spacer(1, 8)])

def nextpage(title):
    flow.append(PageBreak())
    p(title, 'H1Clean')

p('IMO Recruiting Approval Rules', 'TitleClean')
p('Final operating rules | October 8, 2026', 'H2Clean')
p('Target: California public-license leads for Life, final expense, IUL and fixed annuities. Apply these rules to any surname.')
p('A screening pass means the lead fits these rules. It is separate from the father\'s personal approval. Priority and contact readiness are separate decisions.', 'SmallClean')
p('1. Excluded companies and agencies', 'H1Clean')
p('<b>If a relevant current relationship matches an exclusion below, do not add the producer.</b> An acceptable Life relationship elsewhere does not cancel the exclusion.')
table(['Excluded company or agency', 'Apply the rule to'], [
    ['State Farm', 'Relevant current named agency or insurer relationships.'],
    ['Farmers', 'Relevant current named agency or insurer relationships.'],
    ['Allstate', 'Relevant current named agency or insurer relationships.'],
    ['Knights of Columbus', 'Relevant current named agency or insurer relationships.'],
    ['Thrivent', 'Relevant current named agency or insurer relationships.'],
    ['All verified bank or securities agencies', 'Current agency relationships, including newly encountered agencies.'],
], [195, 317])
p('<b>Bank/securities examples:</b> Chase Insurance Agency; Wells Fargo Wealth Brokerage Insurance Agency; Edward Jones Insurance Agency of California; Merrill Lynch Life Agency; LPL Financial. These are examples, not the complete exclusion list.', 'SmallClean')
p('Match the actual relationship', 'H2Clean')
p('Use current agency and insurer entries. Ignore terminated relationships and incidental mentions. State Farm/Farmers include their named insurance entities, such as State Farm Life and Farmers New World Life. Do not extend exclusions to differently named affiliates solely by ownership.', 'SmallClean')
p('<b>Important distinctions:</b> Foremost alone is not a Farmers exclusion. An ordinary Life insurer with "Bank" in its name is not a bank agency. Variable authority alone does not establish a securities-agency relationship. Verify unfamiliar agencies; do not guess.', 'SmallClean')
p('Quick screening sequence', 'H2Clean')
p('1. Match the license number and verify active general Life authority.<br/>2. Check current relationships against the exclusions above.<br/>3. If no exclusion applies, use the eligible profiles on page 2.<br/>4. Record priority and direct-contact readiness separately.<br/>5. Save the source URL, check date and exact reason for the result.', 'SmallClean')
p('<b>PASS:</b> fits these rules. <b>FAIL:</b> an exclusion or verified licensing mismatch applies. <b>REVIEW:</b> concrete record information is missing or ambiguous. A missing qualification record is REVIEW, not proof of inactive Life authority.', 'SmallClean')

nextpage('2. Eligible profiles, priority and contact')
p('These features do not disqualify a producer. A separate exclusion still overrides them.')
table(['Eligible profile', 'How to handle it'], [
    ['WFG and Primerica', 'Established recruiting audiences. Existing organization membership is acceptable.'],
    ['New York Life / NYLIFE and Northwestern Mutual', 'Eligible. Do not apply a general career-agency exclusion.'],
    ['Other Life insurers or agencies', 'Eligible. No single carrier or required carrier count.'],
    ['AssuredPartners, Acrisure, Filice and IMA', 'Eligible. Large or multi-line agency size is not a rejection reason.'],
    ['Gallagher Benefit Services, Mercer Health, Marsh & McLennan and HUB', 'Eligible. Their names or benefits-broker business alone do not trigger exclusion.'],
    ['Life plus health, auto/home or variable qualifications', 'Eligible. Other insurance qualifications do not remove the Life opportunity.'],
    ['Only auto/home or health relationships displayed', 'Eligible, lower priority. Approved counterexamples exist.'],
    ['No agency or insurer relationships displayed', 'Eligible, lower priority. Do not assume no sales or beginner status.'],
    ['New and experienced license holders', 'Eligible. No minimum tenure or production threshold is established.'],
    ['Missing direct contact', 'Save the suitable lead for contact research. Contact absence is not a fit rejection.'],
], [195, 317])
p('Priority: focus effort on visible Life business', 'H2Clean')
p('<b>Higher priority:</b> visible Life-agency relationships or Life appointments aligned with the recruiting focus. WFG and Primerica are established audiences.<br/><b>Lower priority:</b> only auto/home or health relationships displayed, or no agency/insurer relationships displayed. Keep eligible and process after stronger Life-business signals.', 'SmallClean')
p('Auto/home agency membership alone is not a positive target signal. Appointments show relationships, not actual final-expense, IUL or annuity sales. Do not require sales proof from a licensing page.', 'SmallClean')
p('Contact readiness', 'H2Clean')
table(['Contact result', 'Action'], [
    ['READY TO CONTACT', 'Eligible lead with usable direct individual business contact. For phone outreach, use a number that reaches the producer.'],
    ['SAVE - NEEDS CONTACT', 'Missing contact or only shared-office/toll-free numbers. Find direct contact before outreach; keep the otherwise suitable lead.'],
], [155, 357])
p('A higher-priority lead can still need contact research. Earlier shared-office or toll-free inclusions may have been accidental.', 'SmallClean')

nextpage('3. Reference examples and agent handoff')
p('Life-company relationships found among approvals', 'H2Clean')
p('Examples below are positive reference points, not a required-carrier list. Names are shortened. A separate exclusion still applies.', 'SmallClean')
names = [
    'American General', 'Fidelity & Guaranty', 'Life Insurance Co. of the Southwest', 'American National',
    'Nationwide Life and Annuity', 'United of Omaha', 'North American', 'Foresters', 'Transamerica',
    'Athene Annuity and Life', 'SBLI', 'CMFG Life', 'Banner Life', 'Ameritas', 'Baltimore Life',
    'Pruco Life', 'Americo', 'Protective Life', 'Liberty Bankers Life', 'Great Western',
    'Sentinel Security Life', 'John Hancock', 'Guardian Life', 'AAA Life', 'Allianz Life',
    'Lincoln National Life', 'Lincoln Heritage Life', 'EquiTrust Life',
]
table(['Life-company example', 'Life-company example'], [[names[i], names[i+14]] for i in range(14)], [256, 256])
p('Why the boundary decisions are settled', 'H2Clean')
p('<b>Benefits brokers stay eligible:</b> accepted agencies have similar business scope; Gallagher also acquired accepted AssuredPartners. Corporate ownership alone does not establish an exclusion.<br/><b>Banks/securities agencies are excluded:</b> the user confirmed a general rule; no approved agency counterexample was identified in the collected records.<br/><b>Health/P&C-only profiles stay eligible:</b> historical approvals include Manuel Aguilar (health exchange only), Vicky Nava (P&C agency only), and Mario Steven Aguilar and Yohomara Aguilar Martinez (Life appointments with health-oriented insurers only). Another 25 approvals had no agency or insurer entries.', 'SmallClean')
p('What the next agent must save', 'H2Clean')
p('Name and license number; fresh CDI URL and check date; active Life status; exact current relationships and any rule trigger; PASS / FAIL / REVIEW with reason; higher/lower priority; READY TO CONTACT / SAVE - NEEDS CONTACT with contact source; historical approval status separately.', 'SmallClean')
p('Do not reject a lead merely because it was missing from an earlier approved list. Do not invent sales volume, exclusive contracts, beginner status or rejection motives. Verify unfamiliar agency classifications. Record future rule changes when the user confirms them.', 'SmallClean')
p('<b>Basis:</b> 136 supplied approvals, cached CDI evidence checked October 8, 2026, and the finalized decisions in this conversation. This document supersedes earlier questionnaires. It is a screening policy, not a measured accuracy claim or a fresh check of every producer.', 'SmallClean')
p('<b>Public source:</b> <link href="https://cdicloud.insurance.ca.gov/cal/" color="#243B53">California Department of Insurance license lookup</link>. Refresh records for each new screening batch.', 'SmallClean')

def footer(canvas, doc):
    canvas.setFont('Arial', 8)
    canvas.setFillColor(colors.HexColor('#555555'))
    canvas.drawString(50, 25, 'IMO recruiting rules | Finalized October 8, 2026')
    canvas.drawRightString(562, 25, str(doc.page))

path = OUT / 'IMO_Recruiting_Approval_Rules.pdf'
SimpleDocTemplate(str(path), pagesize=(612, 792), leftMargin=50, rightMargin=50, topMargin=40,
    bottomMargin=42, title='IMO Recruiting Approval Rules - Final', author='Recruiting rules').build(
    flow, onFirstPage=footer, onLaterPages=footer)
print('Created', path, 'Pages:', len(PdfReader(path).pages))
