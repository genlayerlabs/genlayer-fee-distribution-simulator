# Owner-funded negative fees: executable proposal

## Shareable summary

Keep the successful appeal return at **2.5 times the bond**, including returned
principal. When a leader appeal or genuine leader-timeout appeal succeeds,
charge the responsible original leader a negative fee large enough to cover
the net correction reward plus a declared bound on other incremental benefits.
Reserve collectible **owner funds before work**, collect the fee from those
funds and burn it. The penalty never becomes another payment to the appellant,
sender, developer or DAO.

Use the same owner-funded collection for existing validator voting negative
fees. Delegators can share staking risks under other policies, but their losses
cannot replace the responsible owner's accountability: an owner can benefit
privately while unrelated delegators pay a pooled penalty. Collection must stay
owner-attributed throughout fee netting and staking, not just at the last debit.

At a 50% success probability, a 2x successful bond return only breaks even before
costs. Keeping 2.5x leaves some cost headroom for independent correction. It is a
calibration, not a universal optimum. Responsibility is based on outcomes,
without trying to classify intent. Reliable service must still have viable
expected economics after error rates, execution costs and capital lockup.

This PR implements an **opt-in simulator policy**, not a deployed fix. Existing
`process_transaction` outputs and contract-vector generation remain the default.
The new entry point settles actual simulator fee output against explicit owner
capital and commitments. It does not change consensus, staking contracts or the
meaning of a successful appeal.

## Exact policy

For participant/source scope s, declare before work:

- `negative_fee_cap`: maximum existing voting negative fees in that scope;
- `correction_bonus_cap`: maximum SUM of net successful leader-appeal rewards
  attributable to that source, not merely one reward or a minimum bond quote;
- `other_gain_bound` G_s: a nonnegative upper bound on all OTHER incremental
  coalition benefits over a justified baseline. Unknown is rejected, not zero.

Reserve their sum against the owner's collectible capital. For realized voting
negative fees V_s and successful leader-correction bonuses R_s, collect:

```text
D_s = V_s + R_s + G_s       if at least one leader correction targets s
D_s = V_s                 otherwise
```

R_s sums actual successful appellant payouts less returned bond principal.
The existing reward helper supplies `floor(5B/2)`, so every bonus is
`floor(5B/2) - B`. G_s is charged once for the aggregate correction episode of
that source; its declared bound must cover that entire episode. This is a
conservative policy: it does not offset the new charge by uncertain forgone
income or reuse an existing voter penalty as deterrence for another reward.

Voting and correction caps are checked separately; spare voter capacity cannot
silently underwrite an enlarged appeal reward. A cap overrun makes the simulation
fail. It does not clip the promised reward, fall back to delegation, or increase
the source's previously accepted cap. A production admission policy must make
these overruns unreachable before accepting the work.

All amounts must be integers in the **same unit as the fee ledger**. The default
simulator stake initialization is synthetic; it is not a collateral certificate.
`OwnerCapital` is the explicit backing input for this policy.

## Source responsibility and scope

`WorkKey(transaction, generation, round_index, validator)` identifies one
participant's contribution over all admitted attempts in that round. The scope
is deliberately round-wide: existing FeeEvents do not identify every voter fee's
rotation. A leader correction additionally records the exact final source
attempt and its actual leader. Earlier rotated leaders and successor leaders
do not inherit the correction charge.

The policy reads the existing canonical appeal classification and raw source
action. An actual proposal timeout selects timeout responsibility; `SKIP_ROUND`
or an LT50 payout label alone does not establish fault. A failed appeal creates
no successful-correction surcharge. Refunded/void appeal bonds in discarded
generations create no new correction charge, while retained historical voting
negative fees are collected once under their original generation identity.

**Validator appeal distinction:** existing minority penalties within a voting
round, including an appeal jury, become owner-funded. An overturned original
committee is still not retroactively penalized simply because the appeal won.
Existing vindication of accurate original dissent survives. Adding a new
original-committee penalty is a separate policy change and would require
revisiting the paper's current settlement assurance.

## API and custody model

`core/owner_liability.py::simulate_owner_funded_fees` accepts:

1. A batch of named `TransactionCase`s, optionally including discarded histories.
2. `OwnerCapital` accounts, aggregated once per economic owner. `self_funds`
   excludes unrelated delegated funds. `other_reserved` covers backing already
   committed to other work, debt or competing slash exposure.
3. Frozen `WorkCommitment`s for every actual admitted participant/source scope.

Every cap for the batch is reserved before any transaction runs. Distinct
validator addresses with a common owner draw from the same capital account.
The function rejects missing/duplicate commitments, contradictory ownership,
insufficient owner funds and unsupported realized exposures. It returns original
and policy fee ledgers, typed source charges, correction evidence, opening and
closing owner capital, and collected burn. Inputs are not mutated.

Existing voting `FeeEvent.burned` entries are collected once, without a second
payoff debit. New leader liabilities append settlement-time burn entries to the
fee ledger; source identity lives in the typed charge record rather than a
mutable payout label. Existing fees, bond principal, rewards and refunds remain
byte-for-byte identical as a prefix of the policy ledger. No added penalty is
used to recompute a sender refund or fund a claimant reward.

The capital result records **this policy's** deductions. It does not pretend to
settle all other staking liabilities. `other_reserved` stays unavailable and
unchanged. The caller must supply a complete competing-liability bound and a
custody rule that prevents those liabilities from consuming this reservation.
If existing custody cannot do that without weakening slashing guarantees, a
separate owner-funded service tranche is necessary.

The batch API consumes supplied terminal outcomes. The reusable
`analysis/liability_reservations.py` book separately models the lifecycle:
immutable commitment, withdrawal of free funds only, final collection/burn and
release. Exact settlement replay has no additional effect; conflicting replay
and early release fail. An asynchronous implementation must retain backing
until actual collection, rather than releasing it on recording nominal debt.

## Guarantees and assumptions

| Checked property | Evidence | Limit |
| --- | --- | --- |
| Owner-only fee incidence | Closing owner funds decrease by each collected charge; delegated funds are unchanged | Beneficial ownership and physical custody are supplied inputs |
| Concurrent backing | Sum of batch caps plus other reservations never exceeds self funds | Other outstanding work and slash exposure must be completely declared |
| No new recipient transfer | Existing reward/refund ledger is an exact prefix; additions are burn-only | Does not certify every existing developer, execution or failed-bond route |
| Correct source | Independent checker reconciles generation, raw leader action, source attempt and successful appeal | Consensus truth/finality is not proved by a fee simulator |
| No duplicated payment | Bond disposal is excluded from new collection; source and event IDs reconcile once | Does not infer hidden economic ownership |
| Bounded coalition incentive | Actual collected correction debit equals R_s + G_s | G_s must bound all other incremental gains relative to the justified baseline |
| Independent appeal reward preserved | Exact 5/2 reward checked against actual FeeEvents | Positive expected return still depends on probability and private cost |

The default fee ledger omits execution reimbursements, complete developer/DAO
flows, externally saved costs and application-value benefits. Those differences
must be bounded in G_s or explicitly excluded from a narrower claim. A zero G_s
is an economic assertion, not a harmless default. The policy cannot establish
a finite bound for arbitrary outside profits.

The source owner is accountable for its authorized operator. The model does
not prove that an independently motivated operator personally bears that loss.
Shared penalty risks can still be a legitimate delegation policy; the guarantee
here specifically requires adequate loss for the accountable owner.

## Proof sketch and executable assurance

**Custody induction.** Let A_o be an owner's available pledged capital and Q_o
the sum of its open caps. Admission requires A_o >= Q_o. Reserve adds a cap only
when the inequality remains true. Withdrawal is limited to A_o - Q_o. Resolving
a cap C with a collected charge D <= C changes available capital to A_o - D and
open reservations to Q_o - C, so remaining free capital changes by C - D >= 0.
Thus settling one obligation cannot consume another's backing. A unique source
resolution prevents replay from applying the transition twice. Owner loss D
is added to burn, so owner capital plus withdrawals plus burn is conserved in
the reservation book. Delegated capital does not enter any transition.

**Conditional incentive inequality.** Suppose a specified coalition includes
the responsible owner, receives correction bonus R_s and has other incremental
benefit g_s <= G_s. Ignore any additional losses or forgone income, conservatively.
The policy collects D'_s = R_s + G_s from that owner, therefore:

```text
incremental coalition payoff <= R_s + g_s - D'_s <= 0
```

Summation extends this to multiple disjoint source scopes only if their payoff
bounds cover every difference without reusing one debit or reservation. This is
an algebraic sufficiency proof conditional on the model assumptions, not a
machine-checked proof of global protocol strategy resistance. It also does not
promise zero honest losses or preserve accurate dissent under arbitrary new
penalty triggers.

`specification/invariants/owner_liability.py` independently recomputes charges
from ordinary fee output and source evidence, rather than trusting charge
totals. Mutation controls reject undercollection, missing or misattributed
corrections, delegated payment, lost competing reserves, altered refunds/rewards,
duplicate voter fees, missing burn and nominal debt without owner loss.

Other tests cover both correction families, failed appeals, voting penalties,
vindication, rotations, historical generations, owner aliases and simultaneous
transactions. Property checks vary large integer capital/gain bounds and verify
the inequality against actual collected losses. A bounded arithmetic certificate
checks 1,440 integer witnesses plus 288 deliberately weakened-loss controls.
The custody tests check every settlement ordering of three obligations.

Run from the repository root:

```sh
python -m pytest -q tests/fee_distributions/test_owner_funded_fees.py \
  tests/fee_distributions/test_liability_reservations.py \
  tests/fee_distributions/test_economic_invariants.py \
  tests/fee_distributions/test_appeal_liability_requirements.py
python -m examples.owner_funded_fees
python -m pytest -q
```

The example uses independent appellants and supplied corrective outcomes. Its
capital limits and G=100 are demonstration inputs, not measured network bounds.
It performs no network actions or transaction-path search.

Local validation of this implementation: **112 focused tests passed**; full
repository suite **1,184 passed, 5 skipped**, with six pre-existing unregistered
marker warnings. The two runnable examples also pass the settlement checker.
These are local simulator results, not contract conformance or E2E results.

## Deployment decision still required

This simulator implementation makes the proposal reviewable. Production work
still needs enforceable pre-work reward/workload ceilings, competing-claim
priority, physical self-fund reservation and source-finality release rules.
Cap growth belongs to admission of future work; an already-promised appeal
must not become unavailable because the original leader later lacks funds.

Capital access also matters: even the bonus-only lower bound grows with the
entire replacement workload. Evaluate peak concurrency, settlement duration,
owner reward share and measured error/cost rates before selecting network caps.
The [proposal evaluation](APPEAL_LIABILITY_EVALUATION.md) compares alternatives
and gives illustrative sizing. The [economic requirements](COALITION_ECONOMIC_CONSTRAINTS.md)
link the appeal-game papers and explain the previous invariant coverage gaps.
