# Recomputation funded by assigned rotations

The 13 September 2026 consensus decision uses the sender's existing per-round
rotation allowance for lazy descendant replay. An ordinary rotation and a lazy
recomputation each spend one extra attempt. Exhaustion cancels the descendant;
it does not erase earned compensation.

`process_transaction(..., discarded_generations=[...])` settles frozen old
histories together with the live generation. The allowance check counts ordinary
rotations in every supplied generation plus one replay for each discarded
generation. Inputs must contain each generation's recorded rounds, without
repeating an earlier generation's records in a later one.

Historical participants retain their time-unit earnings under the existing round
rules. The internal `recomputeInvalidated` mode makes old appeal bonds zero:
the consensus rewind refunds those bonds separately, so they cannot finance
another distribution or appellant reward. Only historical leader/validator work
is carried into final settlement. Sender deposits and refunds are counted once.
The simulator models time units; discarded receipt execution charges remain a
separate consensus CON-668 concern.

Two assigned rotations can fund three unanimous five-validator generations:

```text
Sender funds the original attempt plus two retries
             |
             v
Generation 0: earns 1,100; two rotations remain
             |
             +-- invalidation --> preserve work; spend one rotation
             v
Generation 1: earns 1,100; one rotation remains
             |
             +-- invalidation --> preserve work; spend one rotation
             v
Generation 2: earns 1,100; zero rotations remain
             |
             +-- invalidation --> cancel, settle all 3,300 earned units
```

Generate the independent consensus vectors with:

```sh
python3 scripts/07_generate_consensus_vectors.py --recompute-only --output-dir consensus_vectors
```

The normal full generator also writes `recompute_work.json`. Full regeneration
against parent `09fa779` and this repair produces identical pre-existing vectors;
only the replay vectors are added. The older checked-in consensus vectors have
pre-existing drift from the simulator handoff stack, which this repair does not
silently incorporate.

Validation: 921 fee-distribution tests pass, including five replay-funding tests.
The composed consensus consumer validates zero/one/two retries, shared ordinary
rotation usage, exact validator entitlements, exhausted cancellation, archived
appeal custody, bounded copying and settlement, and idempotent retries.
