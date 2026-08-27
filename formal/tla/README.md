# Endogenous-evaluator attraction model

This directory composes the executable fee certificate with the paper's
non-fee assumptions. It is a new, small population model rather than an
extension of the transaction state machine: the fee simulator remains the
authoritative settlement model, while TLA+ explores the temporal consequences
of its certified payoff kernel.

## Executable chain of evidence

1. `paper_property_sweep.py` derives participant payoffs from actual
   `FeeEvent` output.
2. `PaperFeeKernel.tla` is generated from that report. A Python test fails if
   the checked-in TLA+ values drift from the simulator.
3. `EndogenousEvaluatorAttraction.tla` consumes the four certified spreads and
   checks every task ordering satisfying explicit per-epoch lower bounds.
4. The green TLC configuration checks local basin preservation and bounded
   convergence. Four expected-red campaigns demonstrate that the conclusion
   does not survive removal of its load-bearing assumptions.

Run both layers:

```bash
PYTHONPATH=. python scripts/10_generate_paper_fee_kernel_tla.py --check
PYTHONPATH=. python scripts/11_check_paper_attraction_tla.py
```

The TLC runner needs Java and `tla2tools.jar`. It discovers Homebrew Java and
the Cursor/VS Code TLA+ extension automatically; `--java`, `--jar`,
`JAVA_BIN`, and `TLA2TOOLS_JAR` are explicit overrides.

## Green claim

For the bounded configuration, the generated fee model supplies:

- clear-majority preservation spread: 400;
- successful clear-reversal correction spread: 200;
- `NoMajority` preservation and correction spreads: 0.

The environment supplies deterministic versions of the paper's empirical
bounds:

- the population begins at or above the competent-control threshold;
- every four-task epoch contains at least one settlement-effective surviving
  majority and one successful clear correction;
- the shortcut saves at most 25 per task;
- standing independent capability costs at most 50 per epoch;
- population turnover is bounded to one seat per epoch; and
- a strictly superior strategy gains at least one seat per epoch, with fair
  task and epoch processing.

The worst-case epoch advantage is therefore

```text
1*400 + 1*200 - 4*25 - 50 = 450 > 0.
```

TLC exhausts every allowed ordering and checks:

- the generated TLA+ constants equal the executable fee kernel;
- the realized boundary margin is never below the calculated lower bound;
- competent participation never falls below its bootstrap level or the good
  basin;
- independent correction can fund its modeled standing cost; and
- with strict adoption and fairness, the population reaches and remains at
  full competence within the configured horizon.

## Expected-red results

| Mutation | Counterexample meaning |
|---|---|
| No effective diagnostics | Zero-spread tasks plus costs push the population below the good basin. |
| No vindication | Correction events occur, but a zero original-dissenter reward cannot fund competent correction. |
| Weak payoff response | Non-decreasing adoption preserves the basin but permits permanent stagnation below full competence. |
| Bad bootstrap | Below the control threshold, the majority spread can reinforce the wrong incumbent and drive competence to zero. |

These controls establish the correct high-level conclusion: the fee protocol
can provide a **conditional basin of attraction**. It cannot by itself prove
unconditional bootstrap or convergence.

## Assurance boundary

This is a finite TLC theorem over a five-seat population and bounded epochs.
TLA+ treats diagnostic opportunity bounds, evaluation costs, capability cost,
strict adoption, and scheduling fairness as explicit constants or temporal
assumptions; it does not prove their empirical truth or assign probabilities.

The model also does not yet cover correlated stack lineages, stake-weighted
sampling, chained appeal settlement, validator rotation, the six timeout-only
round-label ambiguities, or simulator-to-Solidity refinement. Those remain
separate composition obligations.

The certified 2.5x appellant return is retained in `PaperFeeKernel.tla` and
checked for drift. It is not treated as a proof of correction frequency:
`MinCorrectionTasks` remains an empirical lower-bound assumption because an
appellant reward alone cannot establish that useful appeals occur or succeed.
