"""Verify and export the paper-facing fee payoff kernel.

Usage:
    PYTHONPATH=. python scripts/09_verify_paper_payoff_kernel.py
    PYTHONPATH=. python scripts/09_verify_paper_payoff_kernel.py --json
"""

import argparse
import json

from src.fee_simulator.analysis.paper_property_sweep import (
    verify_first_rung_paper_properties,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a machine-readable payoff-kernel certificate",
    )
    args = parser.parse_args()

    report = verify_first_rung_paper_properties()
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
        return

    print("PASS: first-rung paper payoff properties")
    print(f"  ordinary vote profiles: {report.normal_profiles_checked}")
    print(
        "  successful appeal profile pairs: "
        f"{report.successful_appeal_profiles_checked}"
    )
    print(
        "    certified through full transaction processing: "
        f"{report.end_to_end_appeal_profiles_checked}"
    )
    print(
        "    all-timeout label ambiguities: "
        f"{report.live_label_ambiguities_detected}"
    )
    print(f"    clear reversals: {report.clear_reversal_profiles_checked}")
    print("    no-majority successes: " f"{report.no_majority_appeal_profiles_checked}")
    print(
        "  maximum vindication: "
        f"{report.maximum_vindicated_count_observed} validators / "
        f"{report.maximum_added_sender_cost_observed} cost units"
    )
    print(
        "  configured-rung boundary cases: "
        f"{report.configured_rung_boundary_cases_checked}"
    )
    print(
        "    largest configured vindication: "
        f"{report.largest_configured_vindication_count} validators / "
        f"{report.largest_configured_added_sender_cost} cost units"
    )
    print("  certified payoff kernel (net units):")
    for path_class, payoff in report.payoff_kernel.items():
        print(f"    {path_class}: {payoff}")
    print("  paper-facing payoff spreads:")
    for margin, value in report.paper_margins.items():
        print(f"    {margin}: {value}")


if __name__ == "__main__":
    main()
