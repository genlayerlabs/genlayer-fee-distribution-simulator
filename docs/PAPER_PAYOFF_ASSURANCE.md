# Paper payoff assurance

This repository treats the executable fee simulator as the authoritative
economic model for the bounded-attraction argument in
`endogenous-evaluators-reframe-v2.md`.  The paper-facing assurance layer does
not redistribute fees independently.  It observes the `FeeEvent` output of the
existing round transformers and certifies the payoff facts required by the
paper.

## Current certificate

Run:

```bash
PYTHONPATH=. python scripts/09_verify_paper_payoff_kernel.py
```

Use `--json` to emit the finite payoff kernel for a later composition model.

The sweep exhausts every `(Agree, Disagree, Timeout)` count profile for the
first normal committee of five and every settlement-valid successful validator
appeal from an accepted original outcome into an appeal committee of seven.
Majority-disagree originals are excluded because the live classifier routes
them through leader appeals. Validator identities are symmetric within each
count class, while the original and appeal committees remain explicitly
identity-disjoint so retroactive vindication is checked by address.

There are 156 such first-rung appeal profile pairs. Of those, 150 are certified
through the full transaction processor: live labeling, appellant bond debit,
round distribution, fee-pot accounting, and emitted sender refund. The
remaining six are the same appeal profile paired with each of the six accepted
original profiles: all seven appeal validators time out. The settlement
handler can price that explicitly labeled profile under the unchanged overturn
rule, but the current
`TransactionRoundResults` representation has no explicit round-type field and
contains neither a leader receipt nor a cast `Agree`/`Disagree` vote. The
labeler therefore cannot distinguish it from a malformed normal round. The
report preserves this as a visible integration ambiguity rather than changing
the protocol rule or dropping the payoff case.

The sweep also checks two extremal profiles at every configured committee-size
rung: the maximum possible original minority vindicated by a clear reversal,
and a `NoMajority` appeal with zero correction spread. Those larger-rung cases
are boundary checks, not exhaustive enumeration of every larger tally.

The certificate establishes over that bounded domain:

1. An aligned validator in an ordinary clear-majority round earns one
   `validatorsTimeout`; a minority validator earns zero and incurs the
   configured penalty.
2. An ordinary `NoMajority` pays every current validator one
   `validatorsTimeout`, so it supplies no preservation spread.
3. A successful appeal committee is settled from its own majority only.
4. A clear successful reversal pays exactly one `validatorsTimeout` to every
   original-round voter matching the new majority.
5. Other original-round validators receive zero and incur no retroactive
   punishment.
6. A successful `NoMajority` appeal creates no original-round vindication.
7. The successful appellant receives exactly the configured 2.5x bond return.
8. Vindication reduces the sender refund by exactly the vindication payout.
9. The vindicated count is bounded by `floor((N - 1) / 2)`; for `N = 5`, the
   maximum added user cost is two validator rewards.

Expected-red tests remove a required vindication, add retroactive punishment,
pay vindication after `NoMajority`, restore a 1.5x appellant return, remove the
appellant bond debit, leave the sender refund unchanged after vindication, and
remove an ordinary minority penalty. Each mutation must be rejected by the
paper-facing checker.

## Composition boundary

This certificate proves protocol-side payoff facts.  It does not prove that:

- production supplies enough settlement-effective diagnostic tasks;
- a candidate shortcut's evaluation-cost saving is below its settlement loss;
- the initial stake-weighted committee is inside the competent basin;
- appeal committees have enough independent correction capacity;
- validator turnover is bounded or payoff-monotone; or
- the Python simulator or current Solidity implementation refines the other.

It also does not certify end-to-end round classification for the six
all-timeout appeal pairs described above; those need explicit round provenance
in the history format (or a separately justified labeling rule).

Those are explicit inputs to the next layer. The bounded TLA+ population model
in `formal/tla/EndogenousEvaluatorAttraction.tla` now consumes a generated,
drift-checked projection of the finite payoff kernel and checks the temporal
implication:

```text
CertifiedPayoffKernel
/\ DiagnosticFrequencyBound
/\ CompetentBootstrap
/\ PreservationMargin
/\ BoundedPayoffMonotoneTurnover
=> []GoodBasin
```

The green model additionally checks convergence under a stronger strict
payoff-response and fairness assumption. Its expected-red campaigns show that
the fee kernel does not imply unconditional convergence: insufficient
settlement-effective diagnostics erode the basin, removing vindication makes
correction uninvestable, weak payoff monotonicity permits stagnation, and a
bad bootstrap lets the majority spread reinforce the wrong incumbent.

## Current Solidity bridge

The existing `genlayer-consensus` fee-finalization suites already replay the
checked-in simulator vectors through the contracts and compare the resulting
per-recipient reward and penalty ledgers. The new conformance layer builds on
that oracle instead of introducing a second Solidity harness:

```text
current Solidity == checked-in consensus vectors
future simulator == checked-in vectors + classified pending delta
```

Generate a rotation-free future corpus and classify that delta with:

```bash
PYTHONPATH=. python scripts/07_generate_consensus_vectors.py \
  --output-dir test_results/future_consensus_vectors \
  --max-length 7 --max-rotations 0

PYTHONPATH=. python scripts/12_check_consensus_vector_conformance.py \
  --consensus-dir /path/to/genlayer-consensus/test/fees/simulator_results \
  --future-dir test_results/future_consensus_vectors \
  --require-red \
  --json-output test_results/consensus_expected_red.json
```

Against consensus revision `7fe5413ff`, the bounded comparison covered 489
shared rotation-free cases. Five no-appeal cases remained exact parity and 484
were expected red. Every red case was explained by one or both pending changes:

1. the fee quote reserves for a 2.5x rather than 1.5x successful-appellant
   return, and a successful appellant receives that 2.5x return on the
   unchanged appeal bond; and
2. a clear successful validator appeal pays the original voters aligned with
   its new majority one validator reward each.

There were zero unclassified reward, penalty, round-shape, vote-outcome, or
accounting deltas. The checker validates future vindication by symbolic
address, rejects wrong-side payments and any retroactive punishment, and
checks the sender refund as the conservation consequence of the larger
upfront reserve and additional payouts.

The canonical one-appeal case has a 1,400 validator-appeal bond. Current
Solidity and its locked vector return 2,100; the future vector returns 3,500
and pays the one vindicated original dissenter 200. The worst-case reserve
increases by 2,300, so the vector refund increases by the residual 700:

```text
2,300 reserve delta - 1,400 appellant delta - 200 vindication = 700 refund delta
```

The unchanged full-integration Solidity choreography remains green against
the checked-in vector and becomes red when pointed at the future vector. The
first on-chain mismatch is the appellant custody (`2,100 != 3,500`); the
corpus classifier independently establishes the missing vindication credit.
This is an expected-red implementation boundary, not a claim that Solidity
already implements the paper fee model.

## Next coverage increments

The highest-value extensions are:

1. rotations and their intermediate settlement entries in the classified
   Solidity delta corpus;
2. direct expected-red per-address assertions for future vindication in the
   Solidity choreography, rather than the current transitive vector proof;
3. broader interior profiles at configured committee-size rungs;
4. an unbounded proof or parameter sweep beyond the current five-participant,
   finite-epoch population model.
