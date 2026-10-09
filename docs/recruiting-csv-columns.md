# Recruiting CSV column choices

User-confirmed presentation choices, October 8, 2026. These change the export,
not the recruiting rules in `imo-final-approval-rules.md`.

Start with Name, Passed_Test (Yes/No), Assessment (short reason), License_URL.
Keep one license number, business address and phone, directions link, source
search ZIPs, California check date and languages.

Keep active qualifications and readable qualification details, with issue dates
only. Keep Life issue date and years since that displayed issue date. This is
elapsed licensing time, not proof of actual years working. Keep active Health,
P&C and variable authority flags.

Keep appointed insurers, appointment row count, unique insurer count, Life
insurers and count, Health insurers, P&C insurers, and readable appointment
details. Keep agency organizations, unique agency count, relationship row count,
Life agencies and readable agency relationship details. Relationship details
include entity, qualification and displayed date. Keep the latest displayed
relationship date and one Rule_Document name identifying the applied rulebook.

Remove duplicate raw search text, input row numbers, duplicate names/check dates/
addresses/phones, source record status, inactive qualification columns, Life
status, expiry/status countdowns, repeated experience notes, phone source/
directness/toll-free/contact-readiness columns, priority, excluded-relationship
and bank-marker columns, other screening statuses, historical approval, AI input,
data notes, assessment-method boilerplate and all JSON columns.

Leave enrichment and results blank for rows not yet checked. Preserve row order
and the source CSV. Do not change screening decisions when changing columns.
