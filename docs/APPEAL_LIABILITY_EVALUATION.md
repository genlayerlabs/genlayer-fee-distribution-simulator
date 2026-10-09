# Appeal liability: proposal evaluation

Reviewed 2026-10-09. This supplements
[Economic requirements across roles](COALITION_ECONOMIC_CONSTRAINTS.md).

**Implementation update:** the resulting proposal is now available as an opt-in
simulator settlement. See [Owner-funded negative fees](OWNER_FUNDED_NEGATIVE_FEES.md)
for the implemented contract, proof assumptions, checks and reproducible example.
The analysis below records the earlier evaluation and its pinned source evidence;
references to unimplemented settlement describe that evaluation stage. The new
layer is based on simulator #36 at `c6f6163caf73889aaff45fbf08f415948c8c2328`.
The default fee policy and all Solidity remain unchanged.

## Recommendation

The strongest candidate among the alternatives reviewed is an outcome-based,
reward-linked negative fee with attributable, committed backing. Retain the
2.5x successful return as the current participation calibration. Reuse the
existing appeal economics, penalty ledger, collection and burn infrastructure.

Do not approve the simpler rule "charge a pool penalty equal to the net appeal
bonus" as a complete solution. The economic actor who receives the benefit
must bear enough of the collectible loss. Current fee penalties can be shared
with unrelated delegators. Timeout compensation and other payoff differences
also need to be included, and the same backing cannot secure unlimited work.

This is a leading design candidate, not a proof of a globally optimal mechanism
or a production-ready fix. The allocation of attributable backing and a complete
bound on additional income remain design obligations. No fee distribution,
appeal classifier, reward multiple, bond quote or staking policy is changed by
this evaluation.

## Agreed design assumptions

- Responsibility follows observable protocol outcomes, without judging intent.
- Honest mistakes may incur negative fees. Zero downside for honest actors is
  not a requirement; positive expected economics for competent service remains.
- A difficult contract may consume user funds for genuine work.
- Specified manipulation must not improve the responsible coalition's payoff.
- Developer/user ownership must not turn participant penalties into their income.
- Independent correction and accurate dissent must remain worthwhile.
- Reuse is preferred, but an existing helper's unrelated side effects are not
  automatically part of the intended policy.

The accountable principal must be explicit. Validator owner, operator and
delegators are not interchangeable economic owners. Treating the validator
owner as responsible for an authorized operator is a principal-agent assumption;
it does not prove that the operator personally bears the owner's losses.

## Evidence and revision boundary

Simulator: `0ff4ba85b0277edb2b64479daf5e560f52688ffe`, the inspected head of
[PR #30](https://github.com/genlayerlabs/genlayer-fee-distribution-simulator/pull/30),
above #29 and #28. Existing local analysis additions are uncommitted.

Consensus source review: `e935a51051435770249ca5b0cf62926c223d0873` on
`codex/con-984-policy-fixes`. The five key files below were fetched again at
that immutable commit and matched the previously reviewed file blobs. This
source review does not assert that these rules are deployed.

| Observation | Evidence | Consequence |
| --- | --- | --- |
| All successful appeal kinds share the reward calculation | [FeeSplitUtils](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/utils/FeeSplitUtils.sol#L208), shared helper at line 480 | Reuse net bonus calculation, including integer rounding |
| Fee penalties have a common accounting, netting and durable-debt path | [TransactionFeesManager](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/fees/TransactionFeesManager.sol#L1303) | No need to invent another general penalty ledger |
| Stake-debited fee penalties are divided between validator and delegated stake | [ValidatorPrimeUtils](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/utils/ValidatorPrimeUtils.sol#L413) | Pool debit is not identical to accountable-owner debit |
| Actual debit is capped by available stake; only collected debt is acknowledged | [Debit caps](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/utils/ValidatorPrimeUtils.sol#L1089), [staking adapter](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/staking/StakingValidators.sol#L687) | Nominal debt alone cannot establish deterrence |
| Timeout outcomes carry extra compensation and failed-bond distributions | [FeeSplitUtils timeout cases](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/utils/FeeSplitUtils.sol#L171) | Count the complete episode, not only the appellant reward |
| Raw proposal timeout is stored separately from settlement labels | [FeesRecorder](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/fees/FeesRecorder.sol#L601) | Reuse provenance; do not infer fault from a mutable payout label |

## The sufficient condition, and its limits

For a specified deviation from a justified honest baseline, define:

- R: appeal bonus, excluding the returned bond principal;
- G: an upper bound on every other incremental benefit to the coalition,
  including extra compensation and saved execution costs;
- F: a lower bound on income forgone relative to the baseline;
- D: a lower bound on additional, collectible NET loss borne by that coalition.

The decomposition must include each payoff difference once, in the same unit.
In particular, F cannot also be counted in D. Then:

```text
coalition payoff improvement <= R + G - F - D
F + D >= R + G  =>  no positive improvement within the stated bounds
```

This is a sufficient accounting inequality, not a proof that a supplied G or
D is correct. Unknown additional benefits are a coverage gap, not zero. An
arbitrary external benefit from changing application state is outside this
fee-only assurance unless explicitly bounded.

The conservative choice is to establish D >= R + G without relying on F.
Existing same-obligation losses may contribute if their attribution and
collectibility are established; do not count one loss against several rewards.

Combining this with the paper's independent-appellant participation condition
gives an explicit feasible reward interval. For success probability q > 0,
bond B, and private appeal cost c, with no outside benefit:

```text
((1-q)B + c) / q < R <= F + D - G
```

The left bound is strict because indifference is not positive participation.
The right bound is the fee-only no-improvement condition above. Evaluate the
actual rounded reward, not an approximate multiplier. If the interval is empty,
changing a coefficient cannot meet both assumptions: the work needs more
attributable backing, a smaller bounded cost/exposure, or a changed incentive
objective. Preserve the interval through admission rather than paying a promised
reward against an unsecured later debit. This is the main acceptance test for
the proposed middle ground.

### Why total pool penalties are insufficient evidence

The current staking implementation divides an assessed fee penalty between
self-stake and delegated stake. An unrelated delegator's loss does not offset
the responsible owner's private appeal income. The required D is the loss of
the relevant economic group after this allocation, fee netting and debit caps.

Simply increasing the pooled penalty until enough reaches the owner is less
attractive than attributable backing: it can impose large external losses,
depends on the ownership fraction, and still needs collection capacity.
Self-funded service liability is the preferred direction, using existing custody
where possible. This needs a clearly defined account and allocation rule; the
current pooled allocation cannot silently be assumed to implement it.

### Backing and time of commitment

For simultaneously outstanding obligations, require:

```text
sum(committed maximum liabilities) <= collectible accountable-owner backing
settled charge for an obligation <= its pre-work committed cap
```

Backing must remain available until the corresponding obligation settles.
Funds allocated to another liability cannot be counted again. Later funding or
rotation changes must not retroactively enlarge an accepted cap. If later
appeal rewards exceed the secured exposure, that mismatch must be resolved
through admission/funding or a new commitment, not hidden as unsecured debt.

The existing debt and withdrawal machinery is useful but its presence alone
does not prove these aggregate exposure bounds. A serving-epoch withdrawal
guard also does not by itself prove that every new fee obligation is covered.

## Concrete candidate: reserve, resolve, collect, release

The next implementation should use one **owner-attributed service-liability
record** for both leader corrections and genuine proposal-timeout corrections.
It should not introduce a second appeal reward formula or another general burn
ledger. The required new semantics are a frozen responsibility, a secured cap,
and the incidence of collection.

| Stage | Proposed contract |
| --- | --- |
| Before assigning work | Identify the liable validator account and its responsible owner; freeze source transaction, generation, round and attempt. Reserve collectible owner funds against the maximum permitted correction exposure. |
| During work and review | Keep the reservation attached to that source through operator changes, rotations, settlement relabeling and recomputation. Other work and withdrawals use only the unreserved balance. |
| Canonical resolution | Derive responsibility from the existing source provenance and final correction outcome. Apply the same liability calculation to leader and timeout correction; retain their distinct existing bond quotes. |
| Collection | Debit attributable funds and burn them. A pending debt entry is not a completed collection. Do not allocate this charge across unrelated delegators or net it against their share of fee income. |
| Release | Release the unused reservation only once all possible charges against that source are final and the assessed charge is collected. Exact settlement retries have no second economic effect. |

The protocol need not identify whether the appellant has the same hidden owner
as the leader: the source account incurs the same liability regardless of the
appellant's identity. The simulator still needs explicit ownership assumptions
to verify coalition payoffs. An authorized independent operator acting against
the capital owner's interests remains a principal-agent limitation.

### Where reuse stops

The reviewed fee ledger nets penalties against validator fee credits **before**
the staking adapter divides the remaining fee income between self and delegated
stake. See [fee-credit forfeiture](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/fees/TransactionFeesManager.sol#L1434)
and [subsequent fee allocation](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/staking/StakingValidators.sol#L717).
Consequently, changing only the final stake debit to self-stake would not
establish owner-only incidence. The new liability must remain attributable
through fee netting, debt recording and collection. Reuse infrastructure with
an explicit incidence category or equivalent separated accounting; do not send
this charge through the existing pooled scalar unchanged.

Self-stake custody is the preferred starting point, but a nominal reservation
is not enough if another slash can consume the same capital first. Available
backing must be net of **all** competing obligations, including existing debt
and overlapping slashing exposure. A segregated tranche or an enforceable
priority/capacity rule must make the combined promises collectible. Do not
silently weaken existing slash guarantees to secure this fee. If existing
custody cannot provide that separation, a separately funded service tranche
becomes necessary; simply increasing the penalty is not a substitute.

The existing [withdrawal guard](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/staking/StakingValidators.sol#L447)
uses the retired slash-epoch frontier. The reviewed
[retirement scan](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/Slash.sol#L638)
waits for tribunal/idleness accounting. This is reusable lifecycle machinery,
but this review has not established that its frontier waits for every proposed
service-fee liability. Connect the release condition explicitly.

Existing [appeal obligation IDs](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/fees/interfaces/IContributionLedger.sol#L24)
and [source generation/rotation provenance](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/fees/FeesRecorder.sol#L36)
provide useful identity anchors. Funding ownership and service responsibility
are different facts: link them, rather than treating the appeal payer's funding
record as proof of who should bear the source's penalty.

### Exposure must be fixed before the service, not at appeal time

For one permitted reward, the conservative reserve is:

```text
cap = successful_appeal_profit(maximum_reward_bond) + other_gain_bound
```

`maximum_reward_bond` means the largest principal allowed to earn a reward
against this source. A minimum bond quote alone is insufficient unless it is
also the enforced reward basis. For several distinct rewards attributable to
one source, reserve their total upper bound; one reservation cannot be counted
in full for each reward. Apply the actual integer formula.

For example, a synthetic reward-bearing bond ceiling of 101 gives a net bonus
of 151 under the existing integer calculation. With a bound of 25 for all
additional benefits, the conservative reserve is 176. Ten concurrent such
obligations require 1,760 distinct units of backing. These are arithmetic
examples, not recommended network parameters or measurements.

For `other_gain_bound`, bound disjoint additional payouts and allowed saved
costs over the complete correction episode. Timeout successor premiums,
additional committee income, execution reimbursements and developer/DAO flows
must be covered when their recipients may belong to the coalition. A conservative
gross funded-payout ceiling can overcount costs and coalition-funded transfers,
but must not omit a funding bucket or assume unlimited later top-ups are bounded.
In particular, the timeout's extra half-leader fee alone is not necessarily all
of G. A tighter bound needs a justified baseline and explicit cost assumptions.

The transaction already pins parts of its
[price/execution profile](https://github.com/genlayerlabs/genlayer-consensus/blob/e935a51051435770249ca5b0cf62926c223d0873/contracts/FeeManager.sol#L1456).
Use those inputs, plus the admitted work/funding envelope, when freezing the
liability cap. If later funding changes the permitted correction exposure,
require a new secured commitment before the affected work. Do not retroactively
increase the old leader's charge, silently reduce the promised appeal reward,
or make an already-promised correction unavailable because the leader later
lacks collateral. Insufficient backing is a **work-admission** constraint.

### What is executable now

`analysis/liability_reservations.py` is an isolated reference model of this
custody contract. It reuses the actual rounded appeal-profit helper and the
earlier liability checks. It keeps commitments immutable, reserves across
concurrent sources, rejects withdrawals of reserved money, settles once and
burns the charge without creating a claimant payout. It treats deposited funds
as already segregated and collectible; it does not claim that ordinary on-chain
self-stake currently satisfies that assumption.

Synthetic tests cover both correction names through the same custody path,
generation/attempt identity, insufficient own backing despite a large unrelated
balance, cap growth, early release, conflicting replay, and every settlement
ordering of three independently funded obligations. The last check independently
reconciles balances, withdrawals and burn after each operation. These are model
controls, not a replay of a production vulnerability or proof that the current
outcome classifier supplies the right responsibility.

The remaining decision gate is now specific: establish a finite, affordable
exposure envelope and a custody allocation that survives all competing claims.
Then connect canonical outcomes to this model and independently reconcile
complete fee ledgers. Until then, the candidate passes a custody-model review,
not a full protocol economics review.

### First capital-sizing check

Even the bonus-only reserve grows with the full correction workload, rather
than with the original leader's individual fee. To expose that tradeoff, take
an illustrative L = V = 100 and compare the bonus with the gross source leader's
L + V = 200 fee. Use the configured normal committee progression 5, 11, 23, 47
and the existing distinct leader/timeout bond bases:

| Source committee | Funded replacement attempts | Leader-correction bonus / gross source fee | Timeout-correction bonus / gross source fee |
| --- | --- | --- | --- |
| 5 | 1 | 9x | 4.5x |
| 5 | 3 | 27x | 13.5x |
| 11 | 1 | 18x | 9x |
| 11 | 3 | 54x | 27x |
| 23 | 1 | 36x | 18x |
| 23 | 3 | 108x | 54x |

These are **lower bounds for the proposed conservative reserve**, with G still
omitted, not complete reserve recommendations. They assume the maximum
reward-bearing bond equals the configured quote and one reward per source.
They are exact arithmetic examples, not observed workload or price data. The
denominator is gross participant compensation; an owner's retained fraction
after delegation can be smaller.

This does not establish that the mechanism is unaffordable: the relevant capital
test is peak outstanding reserves divided by collectible owner capital, and
the relevant return includes the time that capital remains unavailable. It
does show why rotation/committee growth and settlement delay belong in the
evaluation. Raising a flat negative-fee coefficient cannot substitute for this
capacity calculation. Before production implementation, compare the bounded
workload envelopes with available self capital, peak concurrency, settlement
duration and measured error/cost rates. None of those operating measurements
has been established by the current simulator checks.

The simulator's `DEFAULT_STAKE` is a synthetic participant balance. It has no
delegation ownership or reservation ledger, so comparing this table directly
with that default would not establish real collateral sufficiency.

## Timeout and validator coverage

| Outcome family | Existing feature to retain in the evaluation | Required check |
| --- | --- | --- |
| Leader appeal succeeds | Appellant bonus and changed source-round settlement | Full owner payoff bound, correctly attributed original contribution |
| Timeout appeal succeeds | Skipped original round, enhanced successor leader compensation, sender budget refund | Same liability condition; include additional compensation and its source |
| Timeout appeal fails | Successor leader and sender share failed bond principal | Full bond accounting; no invented successful-appeal bonus or duplicate debit |
| Timeout without successful appeal | Half-fee and existing responsiveness rules | Separate ordinary service incentive, not a claim that the appeal surcharge solves all timeouts |
| Rotations and repeated appeals | Different attempts, leaders and bonds | Unique obligation identity and no reuse of one charge to cover several rewards |
| Recomputed or invalidated work | Some work loses downstream applicability without being locally wrong | Use canonical responsibility, not blanket penalties on every skipped/invalidated row |
| Successful validator appeal | Current original-round vindication and zero retroactive punishment | Preserve current assurance until committee responsibility is explicitly redesigned |

The common principle can apply to a single leader or a group, but attribution
differs. Charging an overturned committee is a new policy: specify who is
responsible, preserve vindicated dissent, and demonstrate the relevant coalition
bears enough loss. Total losses across the whole committee are not sufficient
if the benefiting subgroup bears too little. The current paper assurance
explicitly rejects retroactive punishment; changing that choice requires an
updated economic argument and assurance, not merely reusing the penalty helper.

The user/developer property needs funding provenance. Unused sender budget,
failed third-party appeal principal, and extra participant penalties are
different sources. Existing failed-bond refunds must be assessed under an
explicit policy; it would be incorrect to say every possible sender credit is
funded only by that sender. The proposed additional penalty must not create a
new sender refund, developer payment or claimant reward.

## Alternatives compared

| Candidate | Assessment under the agreed requirements |
| --- | --- |
| Raise the ordinary minority coefficient | Insufficient where the relevant settlement never applies that penalty; does not settle liability ownership |
| Reduce total successful return to 2x | No positive incentive at 50% success probability before costs; does not itself eliminate a positive success bonus |
| Block same-address appeals | Does not establish shared economic ownership; unsuitable as the guarantee |
| Pay the correction bounty out of the penalized participant's assets | Gives a claimant a direct interest in obtaining that participant's money; conflicts with the intended funding separation |
| Charge a pooled negative fee equal to the net bonus | Simple, but insufficient without owner incidence, full payoff coverage and backing |
| Retain only the source leader's current fee as security | Insufficient when the correction bonus already exceeds that fee; the sizing table illustrates this even before extra gains |
| Add a separate leader bond | Can establish attributable backing, but does not by itself set the right liability or trigger; consider only if existing custody cannot provide the required guarantee |
| Secure attributable liability through existing infrastructure | Leading candidate: keeps correction incentive and funding separation while minimizing duplicate machinery; requires allocation, cap and attribution rules |

A conservative global collateral threshold plus a hard per-validator work cap
could implement the same backing condition without finely sized reservations,
provided it covers the largest combined exposure and holds through finality.
It is a simpler capacity-policy alternative to evaluate, but can tie up much
more capital. An aggregate reserved-balance counter backed by existing immutable
source records is another implementation choice; the reference model does not
mandate a duplicate on-chain ledger or a new deposit transaction for every job.

This ranking is conditional on the requested objectives. It is not an exhaustive
mechanism-design optimality theorem. A lower reward may later be justified by
measured appeal costs/probabilities; 2.5x is a retained calibration, not a proven
universal optimum.

## Competent participation remains a quantitative constraint

Under a simple two-outcome model, let f be the owner's fee when the work
survives, c its execution cost, e its invalidation probability, and p its own
additional penalty. If invalidation forfeits the fee:

```text
expected service payoff = (1-e)f - e p - c
positive participation requires e < (f-c)/(f+p), when f > c
```

For illustration only, with c = f/2:

| Own penalty / service fee | Break-even invalidation rate |
| --- | --- |
| 1 | 25% |
| 5 | 8.333% |
| 10 | 4.545% |
| 20 | 2.381% |

These are not measurements or forecasts. They show why accepting occasional
mistakes is compatible with penalties, while an arbitrarily large liability
still needs a participation check. Actual timeout branches require their own
compensation in this calculation. The independent-dissenter incentive from the
companion paper remains a separate constraint from appellant profitability.

## Executable evaluation and acceptance boundary

`analysis/appeal_liability_requirements.py` checks the conditional owner-loss
inequality, aggregate backing, committed caps and illustrative leader expected
payoff. Synthetic controls reject shared external losses counted as own losses,
insufficient collection, omitted extra gains, unknown bounds, reused backing and
charges above the committed cap. Property checks exercise the monotone bound
with exact integers; probability calculations use fractions.

The existing owner-payoff adapter was corrected to allow a failed bond's
disposal entry to appear in a successor round. It now validates aggregate bond
coverage per appellant over the complete ledger. It does not claim per-bond
provenance, which needs an obligation identifier absent from FeeEvent.

Run the focused requirements and paper-premise checks with:

```sh
python -m pytest -q tests/fee_distributions/test_economic_invariants.py \
  tests/fee_distributions/test_appeal_liability_requirements.py \
  tests/fee_distributions/test_liability_reservations.py \
  tests/fee_distributions/test_paper_payoff_properties.py \
  tests/protocol/test_appeal_economics.py
```

The implementation acceptance boundary remains:

1. Decide the accountable principal and provide attributable, collectible backing.
2. Freeze liability exposure before work and account for concurrent obligations.
3. Bound the full allowed coalition payoff, including timeout compensation,
   reimbursements, developer payments and any cost savings included in scope.
4. Derive responsibilities from canonical attempts and obligations; settle once.
5. Preserve user-funding separation and ordinary correction incentives.
6. Validate the resulting settlement against independent expectations in the
   simulator and pinned contract conformance fixtures.

The evaluation checks are not a production regression, a deployed-mechanism
certificate, or a search for operational attack paths. No changes were made to
Solidity and no publication, E2E request or deployment was performed.

Validation of this local evaluation: **91 focused tests passed**, including 22
new reservation-model controls. The broader fee-distribution, protocol and
recomputation selection completed with **1,020 passed** in 47.10 seconds.
These results validate the checks and preserve current behavior; they do not
demonstrate that the proposed new settlement satisfies the requirements.
