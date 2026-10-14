#!/usr/bin/env python3
"""Certify the expected-red delta from current Solidity to the future model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fee_simulator.analysis.consensus_vector_conformance import (  # noqa: E402
    compare_vector_directories,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--consensus-dir",
        required=True,
        type=Path,
        help="Current contract-conformant test/fees/simulator_results directory",
    )
    parser.add_argument(
        "--future-dir",
        required=True,
        type=Path,
        help="Vectors emitted by scripts/07_generate_consensus_vectors.py",
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--require-red",
        action="store_true",
        help="Fail if consensus has already reached exact parity",
    )
    args = parser.parse_args()

    report = compare_vector_directories(args.consensus_dir, args.future_dir)
    if args.require_red and report.expected_red_cases == 0:
        raise SystemExit("expected current consensus to be red, but all cases match")

    print("consensus <> future fee-model conformance")
    print(f"  status: {'EXPECTED RED' if report.expected_red_cases else 'PARITY'}")
    print(f"  cases compared: {report.compared_cases}")
    print(f"  exact parity: {report.exact_parity_cases}")
    print(f"  expected red: {report.expected_red_cases}")
    print(f"  appellant gaps: {report.appellant_gap_cases}")
    print(f"  vindication gaps: {report.vindication_gap_cases}")
    print(f"  vindicated validators: {report.vindicated_validators}")
    print(f"  unclassified deltas: {report.unclassified_deltas}")
    print("  aggregate accounting deltas:")
    print(f"    upfront reserve: {report.upfront_reserve_delta}")
    print(f"    appellant payouts: {report.appellant_payout_delta}")
    print(f"    vindication payouts: {report.vindication_payout}")
    print(f"    sender refunds: {report.sender_refund_delta}")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
        print(f"  wrote: {args.json_output}")


if __name__ == "__main__":
    main()
