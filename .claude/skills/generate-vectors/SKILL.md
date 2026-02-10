# /generate-vectors — Generate Test Vectors

Generate compressed JSON test vectors for all valid paths in the TRANSACTION_GRAPH.

## Usage

- `/generate-vectors` — defaults (max-length 16, no variants)
- `/generate-vectors --max-length 7` — limit path length
- `/generate-vectors --max-rotations 2 --max-idle 1` — with variant expansion
- `/generate-vectors --test-mode` — quick test run (10 paths per length)
- `/generate-vectors --max-length 3 --test-mode` — combine flags

## Available Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir` | `path_jsons` | Output directory for JSON files |
| `--max-length` | `16` | Maximum number of edges in path (min 2) |
| `--test-mode` | off | Limit to 10 paths per length for quick testing |
| `--debug` | off | Show detailed error info on failures |
| `--no-filter` | off | Process all paths without filtering |
| `--max-rotations` | `0` | Max leader timeout rotations per normal round |
| `--max-idle` | `0` | Max idle validators per normal round |

## Instructions

Run the following command, passing `$ARGUMENTS` through:

```bash
source /home/jmlago/miniconda3/bin/activate && conda activate kpi-tracker && python scripts/01_generate_test_vectors.py $ARGUMENTS
```

After the run, summarize:
- Number of paths generated per length
- Total paths processed
- Output directory location
- Any errors or invariant failures

Note: With `--max-rotations 2 --max-idle 1`, variant expansion can produce 59K+ variants from 489 base paths. Use `--test-mode` for quick verification.
