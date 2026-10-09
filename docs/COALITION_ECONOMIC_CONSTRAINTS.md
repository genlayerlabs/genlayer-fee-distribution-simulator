# Economic requirements across roles

The [owner-funded negative-fee proposal](OWNER_FUNDED_NEGATIVE_FEES.md) now
implements the selected direction as an opt-in simulator policy, with backing
and collection checks in addition to the comparative checks described here.

For the subsequent proposal comparison, including delegated-stake incidence,
committed backing and timeout coverage, see
[Appeal liability: proposal evaluation](APPEAL_LIABILITY_EVALUATION.md).

This review separates appeal participation, profitable manipulation, and honest
participant liability. The current fee model has not been proved to satisfy all
three. User fees paying for real work on a contentious contract are permitted;
manufactured work must not create incremental profit for its initiator, and a
user/developer must not obtain a transfer from an honest network participant.

The checks added here validate supplied defensive policy fixtures. They do not
generate operational attack paths, reproduce the reported on-chain issue, or
certify production exploitability.

## Paper and reward calibration

The main source is **Multi-Agent Appeal Games in Aggregate Disambiguation
Systems**, in the [paper repository](https://github.com/genlayerlabs/prob-bft-paper/blob/45b6fa3d280d37adbef66da958e6e2c8e02f2485/papers/part4-gametheory/main.tex).
Its [methodology](https://github.com/genlayerlabs/prob-bft-paper/blob/45b6fa3d280d37adbef66da958e6e2c8e02f2485/papers/part4-gametheory/sections/01-methodology.tex)
and [technical appendix](https://github.com/genlayerlabs/prob-bft-paper/blob/45b6fa3d280d37adbef66da958e6e2c8e02f2485/papers/part4-gametheory/sections/appendix-technical.tex)
define the risk-neutral appellant's incremental payoff:

```text
U = q R - (1-q) B + x - c
```

B is bond principal lost on failure, R the NET reward on success, q the subjective
probability of the protocol paying that reward, x private continuation value,
and c execution, monitoring, submission and capital cost. If gross successful
return is mB, then R = (m-1)B. Setting x = 0 gives:

```text
U = (qm - 1)B - c
strict participation: m > (1 + c/B) / q
```

| Gross return | Cost-free break-even probability | Expected payoff at q = 1/2 |
| --- | --- | --- |
| 1.5B | 2/3 | -B/4 - c |
| 2B | 1/2 | -c |
| 2.5B | 2/5 | B/4 - c |

Thus 2B is an indifference boundary at q = 1/2 and zero cost, not a positive
participation incentive. The [earlier design discussion](https://genlayer.slack.com/archives/C072ARC42MC/p1786018726330979)
selected 2.5B to leave bootstrap and operating-cost headroom. This is a policy
calibration, not a universal theorem requiring exactly 2.5B. The appendix's
1.5B protocol description refers to older pinned artifacts; the inspected
simulator stack uses 2.5B. Use actual integer payouts when checking small bonds.

The paper separates bond size (funding, spam resistance, capital access) from
reward calibration. Under its calibrated single-threshold assumptions, the net
reward implementing q* is R = ((1-q*)B + c)/q*. Its no-universal-bond proposition
concerns alignment with social escalation across heterogeneous workloads. It is
not a proof that coalition resistance is impossible, or that this reward is
already coalition resistant. q measures success classification, not truth.

The companion [endogenous-evaluator paper, sections 7.1–7.3](https://github.com/genlayerlabs/prob-bft-paper/blob/45b6fa3d280d37adbef66da958e6e2c8e02f2485/papers/endogenous-evaluator-pressure/README.md)
adds two distinct requirements:

```text
preservation: payoff loss from an inferior shortcut > saved execution cost
correction: w [q_v R_v - (1-q_v) B_v] > standing independent-evaluation cost
```

w is the rate of accurate dissent opportunities. R_v is the original accurate
dissenter's incremental vindication reward, not the appellant's gross return.
Higher conformity penalties can improve preservation while discouraging accurate
dissent and trapping a bad majority. The paper does not require retroactive
punishment of the original committee. The existing simulator assurance chooses
zero settlement for unvindicated members of an overturned validator round.

## Requirements that must hold together

| Requirement | Comparison or bound | Current coverage / limitation |
| --- | --- | --- |
| Leader and appellant under common control | Aggregate all addresses/roles; specified deviation must not outperform matched honest work | New owner-level check; requires justified paired fixtures |
| Developer and user under common control | No incremental transfer from honest leaders/validators to the coalition | User fee legs can be checked; developer payments and payout provenance are unmodeled |
| Honest participant downside | Incremental loss stays within an explicit policy limit for the same work/outcomes | New optional loss limits; no universal zero-loss assumption |
| Difficult contract can consume user budget | User paying for genuine additional work is allowed | Synthetic allowed-cost fixture |
| Honest appeal participation | q * gross return - B - c > 0 at the chosen target q | New exact-arithmetic check; probabilities/costs are assumptions |
| Independent correction remains worthwhile | Correction inequality, including rare opportunity rate | Paper fee kernel covers settlement premises, not real q_v, w or costs |
| Avoid inferior shortcuts | Realized payoff spread exceeds saved computation cost | Paper fee kernel covers spreads; cost savings are unmodeled |
| Failed-appeal funding and solvency | Bond funds promised successor work; sender reserve covers successful appeal costs | Existing bond coverage, quote and recomputation tests |
| Conservation and single charging | Transfers have sources; bond principal debited once; separate penalties | Existing conservation plus new owner accounting; external payment legs absent |
| Capital access, bounded work and liveness | Bonds affordable to capable appellants; quotes finite and funded; finality maintained | Existing bounded path/quote tests; affordability needs economic inputs |

The user/developer property is about extraction. A validator penalty that is
burned is not automatically income to the sender. In this simulator the sender
can receive an unused fee allocation back while a validator separately incurs a
penalty. A refund is not proof that the penalty funded it. Establishing direct
extraction requires payment provenance and the complete ledger. Honest loss
without coalition gain is a separate liability/griefing question.

## Why the existing checks missed the class of issue

1. `no_profit_from_griefing` infers a coalition from addresses that vote in the
   minority more often than the majority. This excludes other adverse behavior
   and does not group different addresses under one owner.
2. It omits undetermined rounds from payoff accounting, and treats successful
   appellants specially only when the same address cast an earlier vote.
3. It checks absolute payoff rather than improvement over matched honest work.
   Honest service can earn money; misconduct can improve on honesty even if one
   address's absolute payoff is negative.
4. `griefing_amplification` checks unsuccessful appeals. Successful appeals need
   their own causal and ownership assumptions. `cost_of_contention` compares a
   posted cost plus nonnegative penalties with that same cost; this does not
   bound a profitable successful deviation.
5. The paper sweep covers accepted validator appeals and their original
   committee. It does not certify leader appeals, which have different proposal
   and settlement semantics.
6. More vote paths with the same disjoint-owner generator and assertions cannot
   supply the missing ownership and baseline assumptions.

These are assertion and model limitations. A larger number of passing path tests
does not by itself establish strategic safety.

## New defensive checks

`specification/invariants/economic.py` supplies `EconomicComparison`,
`owner_net_payoffs`, `check_economic_invariants`, `appeal_expected_payoff` and
`check_appeal_participation`. `check_all_invariants` accepts an optional
`economic_comparison`; legacy calls continue to check only trace invariants.

Provide baseline events, an address-to-owner map spanning both ledgers, deviating
owners, and a rationale explaining matching work/external outcomes. Supply
protected owners and explicit incremental loss limits when relevant. No vote or
round label decides which balance changes to count. Any positive coalition
improvement fails, including one unit. This is stronger than a direct-extraction
check and appropriate only for designated deviations, not ordinary honest
appeals or arbitrary unrelated transactions.

Appellant bond disposal is counted through the original debit, not debited again
as a burn. Validator burns and slashes remain separate liabilities. Opening
stake is not earnings. Missing ownership and unsupported required components
fail closed. Requesting `DEVELOPER` or `receipt_reimbursements`, for example,
returns a coverage failure. Ignoring those components is justified only if they
are absent or cancel under that comparison. A time-unit pass does not certify
token profit, real execution cost, developer revenue or transaction-value gains.

Tests use synthetic ledgers and mutation controls, plus an ordinary honest
simulator transaction to verify integration. They show that conservation can
coexist with forbidden owner-level gain, aliases do not hide that gain,
legitimate work and self-refunds pass, and excessive honest liability and
insufficient appeal incentive fail. They do not replay Y-B01 or claim the
protocol is fixed. A production regression still needs a reviewed, complete
matched settlement fixture and payment provenance.

## Implications for selecting a fix

For a specified successful self-induced appeal, write F for coalition honest
fees forgone and P for an additional enforceable negative fee. Ignoring other
deltas, the necessary no-profit bound is:

```text
F + P >= (m-1)B
```

This conditional accounting constraint is not an expected-value proof over all
outcomes. Include costs, reimbursements, other rewards and failed paths if they
differ. Reducing m reduces the deterrent needed but also reduces independent
appeal participation. Increasing B at fixed m increases the capital barrier and
successful reward; it does not change the cost-free probability threshold.

The ordinary minority negative fee does not settle on every skipped round.
Increasing its coefficient cannot help where the settlement never charges it.
A new negative fee needs an explicit trigger, payer, funding/debt rule and
collection bound. If honest behavior can receive the same charge, test that
downside separately; calling a round wrong does not identify who caused it.

If H is the maximum defensible additional honest liability under the same
trigger, a candidate must satisfy both `P >= max(0, (m-1)B-F)` and `P <= H`.
An empty interval means this uniform penalty cannot satisfy both assumptions.
Revisit attribution, reward eligibility, funding or the success criterion before
choosing a coefficient. This is a conditional design test, not a global
impossibility theorem.

Specify these rules and assumptions first. Then require the same candidate to
pass owner comparisons, honest participation, independent correction, liability
limits, funding and quote conformance together. No economic parameter or fee
distribution rule is changed by this patch.
