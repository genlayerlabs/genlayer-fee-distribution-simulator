#!/usr/bin/env python3
"""
Helper script to run comprehensive path tests with various configurations.

Examples:
    python run_path_tests.py --quick
    python run_path_tests.py --first 1000
    python run_path_tests.py --rounds 13 16
    python run_path_tests.py --range 1000000 1001000
    python run_path_tests.py --estimate
"""

import argparse
import subprocess
import sys
import os
from src.fee_simulator.specification.state_machine.path_analysis.round_combinations import (
    generate_all_paths,
    PathConstraints,
    TRANSACTION_GRAPH,
)


def estimate_paths():
    """Estimate total number of paths for different round counts."""
    print("Estimating path counts by round length...")
    print("=" * 50)

    total = 0
    for rounds in range(1, 33):
        constraints = PathConstraints(
            min_length=rounds + 2,
            max_length=rounds + 2,
            source_node="START",
            target_node="END",
        )

        # Count first 10000 to estimate
        count = 0
        for i, _ in enumerate(generate_all_paths(TRANSACTION_GRAPH, constraints)):
            count += 1
            if i >= 9999:  # Stop at 10k for estimation
                print(f"Rounds {rounds:2d}: 10,000+ paths (stopped counting)")
                total += 10000
                break
        else:
            print(f"Rounds {rounds:2d}: {count:,} paths")
            total += count

    print("=" * 50)
    print(f"Estimated total: {total:,}+ paths")
    print("\nNote: Actual total is likely much higher (133M+)")


def run_tests(args):
    """Run tests based on command line arguments."""
    cmd = ["pytest", "test_all_paths_comprehensive.py"]

    if args.verbose:
        cmd.append("-v")

    if args.quick:
        cmd.extend(["-m", "quick"])
        print("Running quick smoke tests...")

    elif args.first:
        if args.first == 500:
            cmd.extend(["-m", "first_500"])
        else:
            # Custom range
            cmd.extend(["-k", f"test_path_range[0:{args.first}]"])
        print(f"Running first {args.first} paths...")

    elif args.last:
        cmd.extend(["-m", "last_500"])
        print("Running last 500 paths...")

    elif args.rounds:
        min_r, max_r = args.rounds
        if min_r == 13 and max_r == 16:
            cmd.extend(["-m", "rounds_13_to_16"])
        else:
            # Custom round range - would need to implement in test file
            print(f"Custom round range {min_r}-{max_r} not yet implemented")
            return
        print(f"Running paths with {min_r}-{max_r} rounds...")

    elif args.range:
        start, end = args.range
        cmd.extend(["-k", f"test_path_range[{start}:{end}]"])
        print(f"Running paths {start}-{end}...")

    elif args.all:
        response = input(
            "WARNING: This will test ALL paths and take a very long time. Continue? (y/N): "
        )
        if response.lower() != "y":
            print("Aborted.")
            return
        cmd.extend(["-m", "all_paths"])
        print("Running ALL paths (this will take a very long time)...")

    else:
        print("No test option specified. Use --help for options.")
        return

    # Add parallel execution if requested
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])

    # Add output file if requested
    if args.output:
        cmd.extend(["--junit-xml", args.output])

    # Run the tests
    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=os.path.dirname(__file__))
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Run comprehensive path tests for round labeling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --quick                    # Run quick smoke tests
  %(prog)s --first 1000              # Test first 1000 paths
  %(prog)s --rounds 13 16            # Test paths with 13-16 rounds
  %(prog)s --range 1000000 1001000   # Test specific path range
  %(prog)s --estimate                # Estimate total path counts
  %(prog)s --all -n 8                # Test ALL paths with 8 parallel workers
        """,
    )

    # Test selection options (mutually exclusive)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="Run quick smoke tests")
    group.add_argument("--first", type=int, metavar="N", help="Test first N paths")
    group.add_argument("--last", action="store_true", help="Test last 500 paths")
    group.add_argument(
        "--rounds",
        nargs=2,
        type=int,
        metavar=("MIN", "MAX"),
        help="Test paths with specific round count range",
    )
    group.add_argument(
        "--range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="Test specific range of paths",
    )
    group.add_argument("--all", action="store_true", help="Test ALL paths (very slow!)")
    group.add_argument(
        "--estimate", action="store_true", help="Estimate total path counts"
    )

    # Other options
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "-n",
        "--parallel",
        type=int,
        metavar="N",
        help="Number of parallel workers (requires pytest-xdist)",
    )
    parser.add_argument("-o", "--output", metavar="FILE", help="Output results to file")

    args = parser.parse_args()

    if args.estimate:
        estimate_paths()
    else:
        run_tests(args)


if __name__ == "__main__":
    main()
