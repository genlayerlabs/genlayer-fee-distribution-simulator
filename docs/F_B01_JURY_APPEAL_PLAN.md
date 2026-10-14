# F-B01 simulator checkpoint: replay-origin jury appeal

The simulator currently lets a predecessor's `LEADER_TIMEOUT_50_PERCENT` fee
color select `APPEAL_LEADER_TIMEOUT_*`. In the mixed route
`Undetermined → leader replay → ValidatorsTimeout → fresh jury`, the replay's
fee color is LT50, but the admission is a validator jury. This checkpoint is
limited to that route; genuine `LEADER_TIMEOUT` admissions keep their existing
classification and bond basis.

Implementation will classify the jury from the replay's actual decision and
admitted vote route, without using LT50 as an admission type. It will retain
the replay's LT50 work payout until a real overturn, distribute failed-jury
fees plus forfeited bond to aligned jurors with existing division dust, and
use the existing validator-success return and vindication rules on overturn.
The remedy round keeps its actual normal or timeout work type, without LT150
leader-timeout compensation. An all-idle jury returns bond principal through
the existing no-reveal path. No bond, unit fee, or ownership formula changes.

Focused tests will construct the full round sequence and assert route labels,
bond quote, each juror's payout, dust, sender and appellant outcomes, and a
genuine leader-timeout control. A separate F-B01 sidecar will export the same
deterministic cases for Consensus parity if the generic path graph cannot
express the replay-origin admission. The N-B02 ownership corpus and its
immutable obligation IDs remain unchanged. After implementation, regenerate
the full horizon-8/seed-0 Consensus vector corpus in a temporary directory,
compare common legacy files, run the simulator suite, and hand the exact
changed vectors and validation output to the parent for Consensus checks.
