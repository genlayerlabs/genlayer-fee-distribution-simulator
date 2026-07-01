---
name: fee-simulator-use
description: Use the GenLayer fee distribution simulator correctly — simulate scenarios, run exhaustive sweeps, regenerate consensus test vectors, or mirror a contract fee change. Use when asked about GenLayer fee distribution amounts ("who earns what"), appeal bond pricing, changing the fee model, regenerating test/fees/simulator_results vectors, or checking fee parity with genlayer-consensus.
---

# Using the GenLayer Fee Distribution Simulator

## What this repo is (and is not)

The **executable spec of the time-unit fee layer** of `genlayer-consensus` — a Python mirror of `FeesProcessor`/`FeesRecorder`/`FeeManager.calculateMinAppealBond`. It does **not** verify the contracts (it models them; parity is enforced by the vector-driven suites in the consensus repo), does **not** model gas/receipt/storage fees, developer fees, GEN price multiplier, messages or top-ups, and **abstracts validator identity** (compare quantities and roles, never addresses). Full framing: `README.md` (What it is / does / does NOT do).

## Environment

Do not assume `python3` exists on the host. Run everything through nix-shell:

```bash
nix-shell -p "python311.withPackages (ps: [ps.pytest ps.pytest-xdist ps.pydantic ps.tabulate ps.hypothesis ps.numpy ps.rich])" --run "<cmd>"
```

`numpy` is only needed by path-analysis tests, `rich` only by scripts 01–06.

## Entry points

| Task | Entry point |
|---|---|
| Simulate one scenario, see tables | `/simulate <NODE> <NODE> ...` skill, or `path_to_transaction_results()` + `process_transaction()` + `display_summary_table()` |
| Run the test suite | `/test` (994 tests, ~70 s) |
| Exhaustive sweep with invariants | generate paths (`path_generator.generate_all_paths` + `PathConstraints`), run `process_transaction` + `check_all_invariants` per path. Length ≤ 7 ≈ 484 paths; ≤ 9 ≈ 3199 |
| Regenerate consensus vectors | `scripts/07_generate_consensus_vectors.py --max-length 7 --max-rotations 2 --existing-dir <consensus>/test/fees/simulator_results` |
| Incentive analysis | `/analyze-incentives` |
| Inspect the state machine | `/show-graph` |

## Gotchas that cost hours

- **Graph node names**: `LEADER_APPEAL_TIMEOUT_SUCCESSFUL` / `..._UNSUCCESSFUL` (APPEAL before TIMEOUT). There is no `LEADER_TIMEOUT_APPEAL_*` node.
- **Bond formulas are per appeal type** (`core/bond_computing.py`, mirrors `calculateMinAppealBond`): validator appeal = `appeal_size × V` (no leader fee); undetermined leader appeal = `(rot+1) × (L + next_normal_size × V)`; leader **timeout** appeal = `(rot+1) × (L + current_committee_size × V)` (the induced round rotates the existing committee).
- **Vector categorization** = the **last** appeal node in the path; single-round paths need `min_length=2`; vector round types are renamed (`NORMAL`, `SKIP`, `LEADER_TIMEOUT_50%`, `LEADER_APPEAL_SUCCESSFUL`, ...) — see `ROUND_TYPE_MAP` in `scripts/07`.
- **Path length counts edges**, including START/END edges: a single-round transaction is length 2.
- **`rotations` in `TransactionBudget`** is indexed by normal-round sequence (not absolute round index); rotation variants use `rotation_counts={normal_seq_idx: n}`.
- **Amounts are raw time units** (defaults L=100, V=200). On-chain amounts get multiplied by the locked GEN price — never compare absolute wei.

## Changing the fee model (parity discipline)

Contract and simulator implement the same model twice; changes travel in pairs, in this order:

1. Mirror the contract change here (handlers in `core/round_fee_distribution/`, bonds in `core/bond_computing.py`, settlement in `core/refunds.py`).
2. `pytest tests` + an exhaustive sweep (all paths ≤ 9, `check_all_invariants` on each) — both must be fully green.
3. Regenerate vectors with `scripts/07` and copy them into `genlayer-consensus/test/fees/simulator_results/` (the `--existing-dir` mode preserves the complex-scenario pattern keys the hardhat tests look up).
4. Run `genlayer-consensus`'s `test/fees/fee_finalization_tests` suite — that is the parity verdict.

History and precedent: the 18 divergences this discipline exists to prevent are documented in `genlayer-consensus/test/fees/contract_gap_analysis/summary.md`.
