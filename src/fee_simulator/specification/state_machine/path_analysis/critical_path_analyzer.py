"""
Round combinations analysis for critical blockchain fee distribution verification.

This module processes ALL paths without storing them in memory simultaneously.
100% accurate, 0% approximation.
"""

import json
import time
from collections import defaultdict
from typing import Dict, List, Optional, TextIO
from datetime import datetime

from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    PathConstraints,
    Path,
    PathStatistics,
    SPECIAL_NODES,
)
from src.fee_simulator.specification.state_machine.graph import TRANSACTION_GRAPH
from src.fee_simulator.specification.state_machine.path_analysis.path_counter import (
    count_paths_between_nodes,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_generator import (
    generate_paths_lazy,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_display import (
    StatisticsDisplay,
    ProgressReporter,
    PathFormatter,
)


class CriticalPathAnalyzer:
    """
    Analyzer for critical blockchain systems that must verify ALL paths
    without approximation or sampling.
    """

    def __init__(self, constraints: PathConstraints):
        self.constraints = constraints
        self.progress_reporter = ProgressReporter(verbose=True)

    def run_complete_verification(
        self,
        save_paths_to_file: Optional[str] = None,
        save_statistics_every: int = 100_000,
    ):
        """
        Verify ALL paths in the system without storing them all in memory.

        Args:
            save_paths_to_file: Optional file to save all paths (can be very large!)
            save_statistics_every: Save intermediate statistics every N paths
        """
        start_time = time.time()

        # First, get the expected count using matrix method
        print("=" * 70)
        print("BLOCKCHAIN FEE DISTRIBUTION PATH VERIFICATION")
        print("=" * 70)
        print(f"Start time: {datetime.now()}")
        print(f"Constraints: {self.constraints}")

        print("\nPhase 1: Matrix counting for expected totals...")
        expected_result = count_paths_between_nodes(
            TRANSACTION_GRAPH, self.constraints, verbose=True
        )

        print(f"\nExpected total paths: {expected_result.count:,}")
        print(f"Expected by length: {expected_result.by_length}")

        # Initialize counters
        total_processed = 0
        length_distribution = defaultdict(int)
        appeal_distribution = defaultdict(int)
        pattern_frequency = defaultdict(int)
        real_length_distribution = defaultdict(int)

        # Track extreme paths without storing all
        shortest_paths = []
        longest_paths = []
        max_appeal_paths = []
        max_appeals_seen = 0

        # File handle for saving paths if requested
        path_file = None
        if save_paths_to_file:
            path_file = open(save_paths_to_file, "w")
            path_file.write("[\n")  # Start JSON array

        print("\nPhase 2: Processing ALL paths...")
        print("This will process every single path without storing them in memory.")

        try:
            # Process paths one by one using lazy generation
            for path in generate_paths_lazy(TRANSACTION_GRAPH, self.constraints):
                total_processed += 1

                # Calculate statistics for this path
                path_length = len(path) - 1  # Edge count
                length_distribution[path_length] += 1

                # Count real nodes (excluding START/END)
                real_nodes = [n for n in path if n not in SPECIAL_NODES]
                real_length = len(real_nodes)
                real_length_distribution[real_length] += 1

                # Count appeals
                appeal_count = sum(1 for node in path if "APPEAL" in node)
                appeal_distribution[appeal_count] += 1

                # Track patterns
                for node in path:
                    if node not in SPECIAL_NODES:
                        pattern_frequency[node] += 1

                # Track extreme paths (keep only a few examples)
                if len(shortest_paths) < 10:
                    shortest_paths.append(path[:])
                elif path_length < len(shortest_paths[0]) - 1:
                    shortest_paths[0] = path[:]
                    shortest_paths.sort(key=lambda p: len(p))

                if len(longest_paths) < 10:
                    longest_paths.append(path[:])
                elif path_length > len(longest_paths[-1]) - 1:
                    longest_paths[-1] = path[:]
                    longest_paths.sort(key=lambda p: len(p), reverse=True)

                if appeal_count > max_appeals_seen:
                    max_appeals_seen = appeal_count
                    max_appeal_paths = [path[:]]
                elif appeal_count == max_appeals_seen and len(max_appeal_paths) < 10:
                    max_appeal_paths.append(path[:])

                # Save path to file if requested
                if path_file:
                    if total_processed > 1:
                        path_file.write(",\n")
                    json.dump(path, path_file)

                # Progress reporting
                if total_processed % 100_000 == 0:
                    elapsed = time.time() - start_time
                    rate = total_processed / elapsed
                    eta = (expected_result.count - total_processed) / rate

                    print(
                        f"\nProcessed: {total_processed:,}/{expected_result.count:,} "
                        f"({100*total_processed/expected_result.count:.1f}%)"
                    )
                    print(f"Rate: {rate:.0f} paths/sec, ETA: {eta/60:.1f} minutes")
                    print(f"Current length distribution: {dict(length_distribution)}")

                # Save intermediate statistics
                if total_processed % save_statistics_every == 0:
                    self._save_intermediate_statistics(
                        total_processed,
                        length_distribution,
                        appeal_distribution,
                        pattern_frequency,
                        real_length_distribution,
                    )

            # Verify counts match
            print("\n" + "=" * 70)
            print("VERIFICATION COMPLETE")
            print("=" * 70)

            # Check each length
            verification_passed = True
            for length in sorted(
                set(expected_result.by_length.keys()) | set(length_distribution.keys())
            ):
                expected = expected_result.by_length.get(length, 0)
                actual = length_distribution.get(length, 0)
                match = "✓" if expected == actual else "✗"
                print(
                    f"Length {length}: Expected {expected:,}, Actual {actual:,} {match}"
                )
                if expected != actual:
                    verification_passed = False

            print(
                f"\nTotal: Expected {expected_result.count:,}, Actual {total_processed:,}"
            )

            if verification_passed and total_processed == expected_result.count:
                print("\n✓ VERIFICATION PASSED: All paths correctly processed")
            else:
                print("\n✗ VERIFICATION FAILED: Count mismatch detected!")
                print(
                    "CRITICAL ERROR: Blockchain fee distribution verification failed!"
                )

            # Final statistics
            stats = PathStatistics(
                total_paths=total_processed,
                length_distribution=dict(length_distribution),
                appeal_distribution=dict(appeal_distribution),
                real_length_distribution=dict(real_length_distribution),
                pattern_frequency=dict(pattern_frequency),
            )

            # Display results
            print("\nFINAL STATISTICS:")
            StatisticsDisplay.display_path_statistics(stats)

            print("\nExample shortest paths:")
            for i, path in enumerate(shortest_paths[:3], 1):
                print(f"{i}. {PathFormatter.format_path_with_metadata(path)}")

            print("\nExample longest paths:")
            for i, path in enumerate(longest_paths[:3], 1):
                print(f"{i}. {PathFormatter.format_path_with_metadata(path)}")

            if max_appeal_paths:
                print(f"\nPaths with maximum appeals ({max_appeals_seen}):")
                for i, path in enumerate(max_appeal_paths[:3], 1):
                    print(f"{i}. {PathFormatter.format_path_with_metadata(path)}")

            elapsed_total = time.time() - start_time
            print(f"\nTotal processing time: {elapsed_total/60:.1f} minutes")
            print(f"Average rate: {total_processed/elapsed_total:.0f} paths/second")

            return stats, verification_passed

        finally:
            if path_file:
                path_file.write("\n]")  # End JSON array
                path_file.close()
                print(f"\nAll paths saved to: {save_paths_to_file}")

    def _save_intermediate_statistics(
        self,
        processed: int,
        length_dist: Dict[int, int],
        appeal_dist: Dict[int, int],
        pattern_freq: Dict[str, int],
        real_length_dist: Dict[int, int],
    ):
        """Save intermediate statistics to a checkpoint file."""
        checkpoint_file = f"checkpoint_{self.constraints.min_length}_{self.constraints.max_length}_{processed}.json"

        checkpoint_data = {
            "processed": processed,
            "timestamp": datetime.now().isoformat(),
            "constraints": {
                "min_length": self.constraints.min_length,
                "max_length": self.constraints.max_length,
                "source_node": self.constraints.source_node,
                "target_node": self.constraints.target_node,
            },
            "length_distribution": dict(length_dist),
            "appeal_distribution": dict(appeal_dist),
            "real_length_distribution": dict(real_length_dist),
            "top_patterns": dict(
                sorted(pattern_freq.items(), key=lambda x: x[1], reverse=True)[:20]
            ),
        }

        with open(f"checkpoints/{checkpoint_file}", "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        print(f"Checkpoint saved: {checkpoint_file}")


def run_critical_blockchain_verification():
    """Run the complete verification for blockchain fee distribution."""
    constraints = PathConstraints(
        min_length=3,
        max_length=19,  # Full range as required
        source_node="START",
        target_node="END",
    )

    analyzer = CriticalPathAnalyzer(constraints)

    # Run complete verification
    # Optional: save all paths to file (warning: will be huge!)
    # stats, passed = analyzer.run_complete_verification(save_paths_to_file="all_paths.json")

    # Run without saving paths (recommended)
    stats, passed = analyzer.run_complete_verification()

    if not passed:
        raise RuntimeError("CRITICAL: Blockchain verification failed!")

    return stats


if __name__ == "__main__":
    run_critical_blockchain_verification()
