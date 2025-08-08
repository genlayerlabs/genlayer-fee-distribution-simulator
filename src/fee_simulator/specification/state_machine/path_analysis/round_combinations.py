"""
Main orchestration module for round combinations analysis.

This module composes the various components to provide a complete
analysis of transaction paths. It follows the principle of high-level
policy being separate from low-level details.
"""

from typing import Optional, List, Tuple

from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    PathConstraints,
    Path,
)
from src.fee_simulator.specification.state_machine.graph import TRANSACTION_GRAPH
from src.fee_simulator.specification.state_machine.path_analysis.path_counter import (
    count_paths_between_nodes,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_generator import (
    generate_all_paths,
    filter_paths_containing_pattern,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_analyzer import (
    analyze_paths,
    find_extreme_paths,
    find_paths_with_rare_patterns,
    calculate_path_diversity,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_display import (
    StatisticsDisplay,
    PathFormatter,
    ProgressReporter,
    create_summary_report,
)


class TransactionPathAnalyzer:
    """
    High-level orchestrator for transaction path analysis.

    This class coordinates between the various modules to provide
    a complete analysis workflow.
    """

    def __init__(self, constraints: PathConstraints):
        """
        Initialize analyzer with path constraints.

        Args:
            constraints: The constraints for valid paths
        """
        self.constraints = constraints
        self.graph = TRANSACTION_GRAPH

    def run_complete_analysis(self, verbose: bool = True) -> Tuple[List[Path], str]:
        """
        Run a complete analysis of transaction paths.

        Returns:
            Tuple of (all_paths, summary_report)
        """
        reporter = ProgressReporter(verbose)

        # Step 1: Count paths using matrix method
        if verbose:
            StatisticsDisplay.display_header(
                f"Transaction Path Analysis ({self.constraints.source_node} -> {self.constraints.target_node})"
            )
            print(
                f"Length constraints: {self.constraints.min_length} to {self.constraints.max_length}"
            )

        matrix_result = count_paths_between_nodes(
            self.graph, self.constraints, verbose=verbose
        )

        # Step 2: Generate actual paths
        if verbose:
            print("\nGenerating actual paths...")

        all_paths = generate_all_paths(self.graph, self.constraints)

        # Step 3: Verify consistency
        if verbose:
            StatisticsDisplay.display_counting_comparison(matrix_result, len(all_paths))

        # Step 4: Analyze paths
        stats = analyze_paths(all_paths)

        if verbose:
            StatisticsDisplay.display_path_statistics(stats)

        # Step 5: Find interesting paths
        shortest, longest = find_extreme_paths(all_paths)

        if verbose:
            StatisticsDisplay.display_example_paths(
                shortest, "Shortest Paths", max_examples=3
            )
            StatisticsDisplay.display_example_paths(
                longest, "Longest Paths", max_examples=3
            )

        # Step 6: Pattern analysis
        interesting_patterns = [
            "LEADER_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_TIMEOUT",
            "LEADER_APPEAL_TIMEOUT_SUCCESSFUL",
        ]

        if verbose:
            print("\nExample paths with specific patterns:")

        for pattern in interesting_patterns:
            matching = filter_paths_containing_pattern(all_paths, pattern)
            if matching and verbose:
                print(f"\n{pattern} ({len(matching)} total):")
                example = matching[0]
                print(f"  {PathFormatter.format_path(example)}")

        # Step 7: Advanced analysis
        diversity = calculate_path_diversity(all_paths)
        rare_patterns = find_paths_with_rare_patterns(all_paths, threshold=0.01)

        if verbose:
            print(f"\nPath diversity score: {diversity:.3f}")
            if rare_patterns:
                print(f"Found {len(rare_patterns)} rare patterns (< 1% occurrence)")

        # Create summary report
        summary = create_summary_report(stats, shortest, longest)

        return all_paths, summary

    def find_specific_examples(self, pattern: str, count: int = 5) -> List[Path]:
        """
        Find example paths containing a specific pattern.

        This is useful for testing and debugging specific scenarios.
        """
        all_paths = generate_all_paths(self.graph, self.constraints)
        matching = filter_paths_containing_pattern(all_paths, pattern)

        # Sort by length to get simplest examples first
        matching.sort(key=len)

        return matching[:count]


def main():
    """
    Main entry point demonstrating the analysis workflow.
    """
    # Define constraints for valid transaction paths
    constraints = PathConstraints(
        min_length=3,
        max_length=19,
        source_node="START",
        target_node="END",
        max_appeals=16,
    )

    # Create analyzer
    analyzer = TransactionPathAnalyzer(constraints)

    # Run complete analysis
    paths, summary = analyzer.run_complete_analysis(verbose=True)

    # Optionally save summary to file
    # with open("path_analysis_summary.txt", "w") as f:
    #     f.write(summary)

    print(f"\nAnalysis complete. Found {len(paths):,} valid transaction paths.")


if __name__ == "__main__":
    main()
