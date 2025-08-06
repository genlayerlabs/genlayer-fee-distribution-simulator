#!/usr/bin/env python3
"""Quick script to check path generation performance."""

from tests.round_combinations import (
    generate_all_paths,
    PathConstraints,
    TRANSACTION_GRAPH,
)
import time


def check_path_generation():
    """Check how many paths are generated with different constraints."""

    for max_rounds in [5, 7, 10, 15]:
        print(f"\nChecking paths with max {max_rounds} rounds:")
        constraints = PathConstraints(
            min_length=3 + 2,  # min 3 rounds + START/END
            max_length=max_rounds + 2,
            source_node="START",
            target_node="END",
        )

        start_time = time.time()
        count = 0

        for path in generate_all_paths(TRANSACTION_GRAPH, constraints):
            count += 1
            if count % 10000 == 0:
                elapsed = time.time() - start_time
                rate = count / elapsed
                print(
                    f"  Generated {count:,} paths in {elapsed:.1f}s ({rate:.0f} paths/sec)"
                )

            # Stop after 100k to avoid taking too long
            if count >= 100000:
                print(f"  Stopped at {count:,} paths (more exist)")
                break
        else:
            print(f"  Total: {count:,} paths")


if __name__ == "__main__":
    check_path_generation()
