#!/usr/bin/env python3
"""
Analyze paths: generation, counting, and filtering with 1000 validator constraint.

This script shows for each path length:
1. Number of paths from generator (DFS)
2. Number of paths from counter (Matrix)
3. Number of valid paths after filtering
4. Filtering rate
"""

import sys
from tabulate import tabulate
from typing import Dict, List, Tuple
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, ".")

from tests.round_combinations.graph_data import TRANSACTION_GRAPH
from tests.round_combinations.path_generator import generate_all_paths
from tests.round_combinations.path_counter import count_paths_between_nodes
from tests.round_combinations.path_filter import (
    filter_valid_paths,
    analyze_path_distribution,
    find_max_appeal_chain_length,
)
from tests.round_combinations.path_types import PathConstraints


def analyze_paths_by_length(max_length: int = 19) -> List[Dict]:
    """
    Analyze paths for each length, comparing generation, counting, and filtering.

    Returns a list of dictionaries with statistics for each length.
    """
    results = []

    print(f"Analyzing paths up to length {max_length}...")
    print(
        f"Maximum consecutive unsuccessful appeals possible: {find_max_appeal_chain_length()}"
    )
    print("-" * 80)

    # Use tqdm for progress bar
    for length in tqdm(
        range(1, max_length + 1), desc="Processing path lengths", unit="length"
    ):

        # Set up constraints
        constraints = PathConstraints(
            min_length=length, max_length=length, source_node="START", target_node="END"
        )

        # First count paths to see if we need progress tracking
        count_result = count_paths_between_nodes(TRANSACTION_GRAPH, constraints)
        matrix_count = count_result.by_length.get(length, 0)

        # Generate paths using DFS
        if matrix_count > 10000:
            # For large path counts, show a sub-progress bar
            generated_paths = list(
                tqdm(
                    generate_all_paths(TRANSACTION_GRAPH, constraints),
                    desc=f"  Generating paths for length {length}",
                    total=matrix_count,
                    leave=False,
                    unit="paths",
                )
            )
        else:
            generated_paths = generate_all_paths(TRANSACTION_GRAPH, constraints)
        generated_count = len(generated_paths)

        # Matrix count already computed above

        # Filter valid paths (1000 validator constraint)
        if generated_count > 10000:
            # For large path counts, show progress for filtering
            from tests.round_combinations.path_filter import is_valid_path

            valid_paths = []
            for path in tqdm(
                generated_paths,
                desc=f"  Filtering paths for length {length}",
                leave=False,
                unit="paths",
            ):
                if is_valid_path(path, max_addresses=1000):
                    valid_paths.append(path)
        else:
            valid_paths = filter_valid_paths(generated_paths, max_addresses=1000)
        valid_count = len(valid_paths)

        # Calculate filtering statistics
        if generated_count > 0:
            validity_rate = (valid_count / generated_count) * 100
            filtered_count = generated_count - valid_count
        else:
            validity_rate = 0.0
            filtered_count = 0

        # Analyze address usage for valid paths
        if valid_paths:
            # Get detailed analysis
            analysis = analyze_path_distribution(valid_paths)
            avg_addresses = analysis["address_usage"]["average"]
            max_addresses = analysis["address_usage"]["max"]
            min_addresses = analysis["address_usage"]["min"]
        else:
            avg_addresses = max_addresses = min_addresses = 0

        results.append(
            {
                "length": length,
                "generated": generated_count,
                "matrix": matrix_count,
                "valid": valid_count,
                "filtered": filtered_count,
                "validity_rate": validity_rate,
                "avg_addresses": avg_addresses,
                "max_addresses": max_addresses,
                "min_addresses": min_addresses,
                "match": "✓" if generated_count == matrix_count else "✗",
            }
        )

    return results


def print_results_table(results: List[Dict]):
    """Print results in a formatted table."""

    # Prepare data for main table
    table_data = []
    total_generated = 0
    total_valid = 0
    total_filtered = 0

    for r in results:
        table_data.append(
            [
                r["length"],
                f"{r['generated']:,}",
                f"{r['matrix']:,}",
                r["match"],
                f"{r['valid']:,}",
                f"{r['filtered']:,}",
                f"{r['validity_rate']:.1f}%",
                f"{r['avg_addresses']:.0f}" if r["avg_addresses"] > 0 else "-",
                (
                    f"{r['min_addresses']}-{r['max_addresses']}"
                    if r["max_addresses"] > 0
                    else "-"
                ),
            ]
        )
        total_generated += r["generated"]
        total_valid += r["valid"]
        total_filtered += r["filtered"]

    # Add totals row
    total_validity_rate = (
        (total_valid / total_generated * 100) if total_generated > 0 else 0
    )
    table_data.append(
        [
            "TOTAL",
            f"{total_generated:,}",
            "-",
            "-",
            f"{total_valid:,}",
            f"{total_filtered:,}",
            f"{total_validity_rate:.1f}%",
            "-",
            "-",
        ]
    )

    headers = [
        "Length",
        "Generated\n(DFS)",
        "Counted\n(Matrix)",
        "Match",
        "Valid\n(1000 limit)",
        "Filtered\nOut",
        "Validity\nRate",
        "Avg\nAddresses",
        "Address\nRange",
    ]

    print("\n" + "=" * 120)
    print("PATH ANALYSIS: Generation, Counting, and Filtering")
    print("=" * 120)
    print(tabulate(table_data, headers=headers, tablefmt="grid", numalign="right"))

    # Additional insights
    print("\nKEY INSIGHTS:")
    print(f"• Total theoretical paths: {total_generated:,}")
    print(
        f"• Paths valid with 1000 validators: {total_valid:,} ({total_validity_rate:.1f}%)"
    )
    print(f"• Paths filtered out: {total_filtered:,}")

    # Find when filtering becomes significant
    for r in results:
        if r["validity_rate"] < 90 and r["generated"] > 0:
            print(
                f"• Filtering becomes significant at length {r['length']} (validity rate: {r['validity_rate']:.1f}%)"
            )
            break

    # Find when all paths are filtered
    for r in results:
        if r["valid"] == 0 and r["generated"] > 0:
            print(f"• All paths filtered out starting at length {r['length']}")
            break


def analyze_filtered_paths_details(max_length: int = 10):
    """Show examples of filtered vs valid paths for shorter lengths."""
    print("\n" + "=" * 120)
    print("FILTERED PATH EXAMPLES")
    print("=" * 120)

    for length in tqdm(
        range(7, min(max_length + 1, 11)),
        desc="Analyzing filtered examples",
        unit="length",
    ):
        constraints = PathConstraints(
            min_length=length, max_length=length, source_node="START", target_node="END"
        )

        # Generate all paths
        all_paths = generate_all_paths(TRANSACTION_GRAPH, constraints)
        valid_paths = filter_valid_paths(all_paths, max_addresses=1000)

        if (
            len(all_paths) > len(valid_paths) and len(all_paths) < 20
        ):  # Only show if some filtered and not too many
            print(f"\nLength {length}: {len(valid_paths)}/{len(all_paths)} paths valid")

            # Find filtered paths
            filtered_paths = [p for p in all_paths if p not in valid_paths]

            # Show up to 3 examples of filtered paths
            for i, path in enumerate(filtered_paths[:3]):
                # Count appeals
                appeal_count = sum(1 for node in path if "APPEAL" in node)
                print(f"  Filtered: {' → '.join(path[1:-1])} ({appeal_count} appeals)")

            if len(filtered_paths) > 3:
                print(f"  ... and {len(filtered_paths) - 3} more filtered paths")


def main():
    """Main analysis function."""
    # Analyze paths up to length 19
    results = analyze_paths_by_length(max_length=19)
    max_appeals = 9

    # Print main results table
    print_results_table(results)

    # Show some examples of filtered paths
    analyze_filtered_paths_details(max_length=10)

    # Additional analysis on appeal chains
    print("\n" + "=" * 120)
    print("APPEAL CHAIN ANALYSIS")
    print("=" * 120)

    print(f"Maximum consecutive unsuccessful appeals possible: {max_appeals}")

    # Calculate theoretical address usage for max appeal chain
    # Normal round (5) + appeals with sizes: 7, 11, 23, 47, 95, 191, 383, 767...
    sizes = [5, 7]  # Start with normal and first appeal
    appeal_sizes = [13, 25, 49, 97, 193, 385, 769]

    for i in range(max_appeals - 1):
        if i < len(appeal_sizes):
            sizes.append(appeal_sizes[i] - 2)  # Reduce by 2 for unsuccessful
        else:
            sizes.append(1000)  # Would hit limit

    cumulative = []
    total = 0
    for s in sizes:
        total += s
        cumulative.append(total)

    print("\nAddress usage for maximum appeal chain:")
    for i, (size, cum) in enumerate(zip(sizes, cumulative)):
        if i == 0:
            round_type = "Normal round"
        elif i == 1:
            round_type = "First appeal"
        else:
            round_type = f"Appeal {i} (unsuccessful)"
        print(f"  {round_type}: {size} addresses (cumulative: {cum})")
        if cum >= 1000:
            print(f"  → Limit reached!")
            break


if __name__ == "__main__":
    main()
