# Acceptance cases

| Case | Concrete inputs | Expected outcome |
| --- | --- | --- |
| Search | city Irbid, home service covering Amman/Zarqa | Service excluded; empty state if no match |
| Roles | register role `admin`; patient accesses operations | Invalid choice; HTTP 403 for operations |
| Booking | approved provider, free future slot, Amman address, JOD 35.125 | Persistent `requested` record, unpaid, total 35.125, history and two in-app updates |
| Validation | address `x`; no acknowledgment; city Irbid outside coverage | Field errors; valid entries preserved; no record or stock/slot changes |
| Concurrency | two submissions for same slot | Exactly one reservation; second rejected |
| Overlap | second service starts 15 minutes into 45-minute reservation | Rejected even when the service ID differs |
| Stale quote | service price changes from 35.125 to 40.000 | Reject old signed quote, ask user to review price |
| Order | quantity 2 × JOD 14.750, stock 3 | Total 29.500, stock 1, unpaid request |
| Basket | JOD 14.750 kit + 8.500 thermometer, same pharmacy | Two snapshotted lines; total 23.250; atomic stock decrements |
| Inventory failure | quantity 2, remaining stock 1 | No order; specific failure; no partial stock deduction |
| Cancellation | cancel same pending order twice | First restores stock; second 403 and no second restoration |
| History/privacy | another patient reads a request or private license | HTTP 403; owner/admin can access correct records |
| Upload | PDF with wrong magic bytes, or file >5 MB | Rejected; valid PDF stored privately and provider pending |
| Review | staff reviews complete license and adds notes | Approved and visible; repeat stale review 409 |
| Catalog conflict | edit with revision 0 when stored revision is 1 | Reject overwrite, preserve current stock |
| Service duration | change duration while active reservations exist | Reject conflicting change |
| Payment | submit payment without gateway | HTTP 503, no paid state, no commission accrual |
| Commission | admin confirms 12.50% / JOD rule | Future JOD records snapshot 12.50; accrued commission remains zero while unpaid |
| Addresses | patient chooses owned saved address | Persist checkout default; other patients cannot edit/delete it |
| Issues | owner submits >=15 characters; admin resolves | Stored issue, resolution, activity, and in-app updates; no refund claim |
| UI | keyboard operation and viewport 360px | Labeled inputs, visible focus, working navigation, no document overflow |

These are test inputs, not seeded real providers or approved financial business rules. Live paid checkout and payout acceptance remain blocked by the missing gateway and business policies.
