# /analyze-incentives — Analyze Incentive Alignment

Run the incentive analysis to show net financial outcomes by validator strategy across all transaction paths.

## Usage

- `/analyze-incentives` — defaults (max-length 16, all paths)
- `/analyze-incentives --max-length 5` — shorter analysis
- `/analyze-incentives --sample-size 100` — sample 100 paths per length
- `/analyze-incentives --csv` — also export as CSV

## Available Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--max-length` | `16` | Maximum path length to analyze |
| `--sample-size` | `0` | Sample size per path length (0 = all paths) |
| `--output` | `incentive_alignment_data.json` | Output JSON file |
| `--csv` | off | Also export results as CSV |

## Strategies Analyzed

The script categorizes participants into four strategies and computes net financial outcomes:

- **Honest Majority** — validators who vote with the majority
- **Dissenting Minority** — validators who vote against the majority
- **Idle Validator** — validators who don't participate (timeout/idle)
- **Frivolous Appellant** — appellants who file unsuccessful appeals

## Instructions

Run the following command, passing `$ARGUMENTS` through:

```bash
source /home/jmlago/miniconda3/bin/activate && conda activate kpi-tracker && python scripts/03_analyze_incentives.py $ARGUMENTS
```

After the run, summarize the key findings:
- Net outcome per strategy (positive = profitable, negative = costly)
- Whether honest behavior is incentivized (honest majority should have best outcome)
- Whether griefing is discouraged (frivolous appeals should be costly)
- Any surprising results
