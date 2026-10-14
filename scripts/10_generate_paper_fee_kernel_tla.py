"""Generate or verify the TLA+ projection of the executable fee certificate.

Usage:
    PYTHONPATH=. python scripts/10_generate_paper_fee_kernel_tla.py
    PYTHONPATH=. python scripts/10_generate_paper_fee_kernel_tla.py --check
"""

import argparse
from pathlib import Path

from src.fee_simulator.analysis.paper_fee_kernel_tla import (
    render_paper_fee_kernel_tla,
)
from src.fee_simulator.analysis.paper_property_sweep import (
    verify_first_rung_paper_properties,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "formal" / "tla" / "PaperFeeKernel.tla"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the checked-in module differs from the fee simulator",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="generated TLA+ module path",
    )
    args = parser.parse_args()

    rendered = render_paper_fee_kernel_tla(verify_first_rung_paper_properties())
    output = args.output.resolve()

    if args.check:
        if not output.exists() or output.read_text() != rendered:
            raise SystemExit(f"STALE: {output}; regenerate it with this script")
        print(f"PASS: {output} matches executable FeeEvent output")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered)
    print(f"WROTE: {output}")


if __name__ == "__main__":
    main()
