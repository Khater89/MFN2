# Product decisions

Confirmed by user: Jordan; JOD. Appointment timezone: Asia/Amman, explicitly displayed. English/LTR follows the PRD's interface choice. Arabic/RTL remains a future decision.

Selected architecture: the PRD's Django alternative; Django 5.2 LTS, Python 3.12, server-rendered UI with progressive enhancement, and SQLite for a single-instance shared development database. No browser-only simulated persistence. No subscriptions, EHR, insurance, ambulance, lab, or video-call infrastructure.

Demo records: explicit sample markers, no ratings, no fabricated usage statistics, no usable sample passwords. “Approved” fixture status demonstrates public listing behavior only; it does not certify an actual clinician.

Current rules:

| Rule | Inputs and outcome | Limits / source |
| --- | --- | --- |
| Verification | Pending/rejected providers cannot publish or transact; staff reviews private documents | PRD 06/07; approval operation is manual |
| Serviceability | Case-insensitive exact city match against comma-separated service areas | PRD 07; city-level matching, no geocoding |
| Reservation | Slot must be future, free, and not overlap another active appointment for the merchant | PRD FR-05; SQLite transaction begins with a write before checking |
| Stock | Positive quantity up to 50, available stock rechecked and decremented atomically | PRD catalog/checkout; cap is an explicit MVP operational limit |
| Prices | Decimal JOD amounts stored to 0.001 JOD; total = sum(quantity × unit price) | Jordan currency precision; no patient surcharge or invented fees |
| Quotes | Signed to user and current price/currency; expire in 15 minutes | Engineering choice to prevent silent stale-price checkout |
| Commission | Unset by default; admin-confirmed percent of merchant gross, per currency, snapshotted | PRD commission requirement; percentage model is a proposed supported business rule, requires explicit admin acceptance |
| Accrual | Zero until verified gateway evidence | PRD forbids claiming successful payment without integration |
| Request cancellation | Patient or merchant can cancel a pending unpaid request; reserves released once | Development request withdrawal only, not a financial refund policy |
| Editing | Revisions reject stale provider/catalog/service/policy edits | PRD FR-06; no last-write-wins for editable records |
| Notifications | Account, license, request, order, status, and issue events stored for relevant users | In-app only; no email/SMS delivery claim |

Outstanding launch decisions: gateway; commission rate and agreed formula; payout schedule; consultation modality; pharmacy delivery vs pickup and logistics; prescription compliance; cancellation/refund/reschedule policies; Arabic support; medical verification authority; retention and consent rules. These are recorded as unresolved; no document instruction overrides the user's confirmed Jordan/JOD choices.
