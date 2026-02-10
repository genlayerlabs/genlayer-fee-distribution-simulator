# /test — Run the Test Suite

Run the full pytest test suite or a specific subset for the GenLayer Fee Distribution Simulator.

## Usage

- `/test` — run the full suite (~994 tests, 5 skipped)
- `/test round_labeling` — run tests in a specific directory
- `/test -k appeal` — pass pytest flags through
- `/test tests/fee_distributions/simple_round_types_tests/test_normal_round.py` — run a specific file

## Instructions

Run the following command, appending any user-provided `$ARGUMENTS` after `pytest`:

```bash
source /home/jmlago/miniconda3/bin/activate && conda activate kpi-tracker && pytest tests/ --tb=short -q $ARGUMENTS
```

If the user specifies a test directory name without the full path (e.g., `round_labeling`), expand it to `tests/<name>/`. If the user passes pytest flags like `-k`, `-x`, `-v`, `--tb`, or `-s`, append them directly.

After the run, summarize:
- Total passed / failed / skipped / errors
- If there are failures, show the first few failure details
- If all pass, confirm the suite is green
