# Hard set (held-out) — design note

Date: 2026-11-08. Data: `data/hard/claims.json`, `data/hard/answer_key.json`. Same customers and policy wordings as the main set.

**Why:** on the main set one big prompt scored 100%, and the workflow fixes were tuned on those same 30 claims. The hard set is new claims that no prompt was tuned on, built to find where one big prompt starts to fail.

**What makes it harder** (30 claims: 10 car, 10 water damage, 5 travel medical, 5 cancellation):
- **Conflicting numbers:** garage quote vs assessor's report; repair quote vs assessor (once the assessor is higher); towing receipt next to the repair cost.
- **Sums:** quotes and receipts with many lines and no total; refunds spread over several letters.
- **Buried facts:** the real driver, a corroded pipe, a pre-existing condition, a call-up date, all inside longer text.
- **Extra attachments:** last year's assessor's report, a vehicle registration named "license", a receipt for a friend.
- **Routing traps:** a car flooded in a parking garage (car, not water damage); a home flood found after a holiday (water damage, not travel).
- **Date edges:** event on the last policy day (covered); treatment two days before the trip; follow-up after the trip.

**Rules for the key:** same decisions and payout order as the main set. "Approve partial" also covers "part of the claim excluded" (a friend's receipt, a visit after the trip), which the level-3 code cannot express on its own (its payout code decides full vs partial from rate and cap only). This is kept on purpose: it is a real limit of "code does the math".

**Status:** answer key drafted by Claude and approved by the author before the run. After the run the author ruled on H-WAT-01: the burst water heater itself is not covered (partial 8,350, was full 10,350). Scores are re-computed from the saved runs; nothing was re-run.
