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

The normal full generator also writes `recompute_work.json`. The combined
JM/Claudio/Kiril candidate includes #30 at
`0ff4ba85b0277edb2b64479daf5e560f52688ffe` and #32 at
`c5c4b42e4be3d5bf930031db41e943836e7d2059`. The full composed test suite
passes 1051 tests, with five skipped.

The two APIs exercise different input boundaries: `process_transaction` accepts
complete, non-overlapping histories; the funded-recomputation model also accepts
interrupted captures and the incremental lifetime checkpoint state consumed by
the Consensus regression adapter. Both preserve earned work, share the funded
retry allowance, and exclude invalidated appeal bonds from rewards.

Full Consensus corpus regeneration must use `--max-length 8 --seed 0` to retain
the existing path-length horizon. `--existing-dir` preserves complex pattern
keys. The generator defaults to length seven; that default is insufficient for
this consumer's corpus. Protocol-invalid post-validator-review ladders are
filtered by the current model. Generated vectors and live Consensus parity
remain separate required checks; Python unit tests alone do not qualify them.

The combined Consensus implementation checkpoints historical work before
recorder reset, preserves interrupted captures, and uses canonical resumed
terminal settlement. The retired archive-copy mechanism is not the consumer
implementation. Actual staking custody, receipt costs and cross-contract
continuation are qualified in Consensus, not asserted by this time-unit model.
