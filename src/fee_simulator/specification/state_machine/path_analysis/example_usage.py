"""
Example usage of the round combinations analysis system.

This file demonstrates various ways to use the refactored modules.
"""

from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    PathConstraints,
)
from src.fee_simulator.specification.state_machine.graph import TRANSACTION_GRAPH
from src.fee_simulator.specification.state_machine.path_analysis.path_counter import (
    count_paths_between_nodes,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_generator import (
    generate_all_paths,
    generate_paths_lazy,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_analyzer import (
    analyze_paths,
    find_extreme_paths,
    group_paths_by_feature,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_display import (
    PathFormatter,
    StatisticsDisplay,
)
from src.fee_simulator.specification.state_machine.path_analysis.round_combinations import (
    TransactionPathAnalyzer,
)


def example_1_basic_counting():
    """Example 1: Count paths without generating them."""
    print("\n=== Example 1: Basic Path Counting ===")

    constraints = PathConstraints(
        min_length=3, max_length=5, source_node="START", target_node="END"
    )

    result = count_paths_between_nodes(TRANSACTION_GRAPH, constraints, verbose=True)

    print(f"\nTotal paths: {result.count}")
    print(f"By length: {result.by_length}")


def example_2_pattern_analysis():
    """Example 2: Find paths with specific patterns."""
    print("\n=== Example 2: Pattern Analysis ===")

    constraints = PathConstraints(
        min_length=3, max_length=7, source_node="START", target_node="END"
    )

    # Generate paths
    paths = generate_all_paths(TRANSACTION_GRAPH, constraints)

    # Group by pattern
    appeal_groups = group_paths_by_feature(
        paths, lambda p: "UNSUCCESSFUL" in " ".join(p)
    )

    print(f"\nPaths with unsuccessful appeals: {len(appeal_groups.get(True, []))}")
    print(f"Paths without unsuccessful appeals: {len(appeal_groups.get(False, []))}")

    # Show an example
    if True in appeal_groups and appeal_groups[True]:
        example = appeal_groups[True][0]
        print(f"\nExample unsuccessful path:")
        print(f"  {PathFormatter.format_path(example)}")


def example_3_lazy_generation():
    """Example 3: Memory-efficient lazy path generation."""
    print("\n=== Example 3: Lazy Path Generation ===")

    constraints = PathConstraints(
        min_length=3, max_length=10, source_node="START", target_node="END"
    )

    # Process paths one at a time without storing all in memory
    pattern_counts = {}
    path_count = 0

    for path in generate_paths_lazy(TRANSACTION_GRAPH, constraints):
        path_count += 1

        # Count patterns
        for node in path:
            if "APPEAL" in node:
                pattern_counts[node] = pattern_counts.get(node, 0) + 1

        # Show progress every 1000 paths
        if path_count % 1000 == 0:
            print(f"  Processed {path_count} paths...")

    print(f"\nTotal paths processed: {path_count}")
    print("\nTop appeal patterns:")
    for pattern, count in sorted(
        pattern_counts.items(), key=lambda x: x[1], reverse=True
    )[:5]:
        print(f"  {pattern}: {count}")


def example_4_complete_analysis():
    """Example 4: Complete analysis with custom constraints."""
    print("\n=== Example 4: Complete Analysis ===")

    # Analyze medium-length paths
    constraints = PathConstraints(
        min_length=5, max_length=9, source_node="START", target_node="END"
    )

    analyzer = TransactionPathAnalyzer(constraints)
    paths, summary = analyzer.run_complete_analysis(verbose=False)

    # Custom analysis
    stats = analyze_paths(paths)

    print(f"\nFound {len(paths)} paths")
    print(
        f"Most common length: {max(stats.length_distribution.items(), key=lambda x: x[1])}"
    )

    # Find shortest path with 2+ appeals
    multi_appeal_paths = [p for p in paths if sum(1 for n in p if "APPEAL" in n) >= 2]

    if multi_appeal_paths:
        shortest_multi = min(multi_appeal_paths, key=len)
        print(f"\nShortest path with 2+ appeals:")
        print(f"  {PathFormatter.format_path_with_metadata(shortest_multi)}")


def example_5_custom_graph_analysis():
    """Example 5: Analyze a custom graph structure."""
    print("\n=== Example 5: Custom Graph Analysis ===")

    # Create a simplified graph for testing
    simple_graph = {
        "START": ["A", "B"],
        "A": ["C", "END"],
        "B": ["C"],
        "C": ["END"],
        "END": [],
    }

    constraints = PathConstraints(
        min_length=2, max_length=4, source_node="START", target_node="END"
    )

    # Count paths
    result = count_paths_between_nodes(simple_graph, constraints)
    print(f"\nPaths in simple graph: {result.count}")

    # Generate and display all paths
    paths = generate_all_paths(simple_graph, constraints)
    print("\nAll paths:")
    for i, path in enumerate(paths, 1):
        print(f"  {i}. {' -> '.join(path)}")


def main():
    """Run all examples."""
    examples = [
        example_1_basic_counting,
        example_2_pattern_analysis,
        example_3_lazy_generation,
        example_4_complete_analysis,
        example_5_custom_graph_analysis,
    ]

    print("Round Combinations Analysis - Usage Examples")
    print("=" * 50)

    for example in examples:
        example()
        print()  # Space between examples

    print("\nAll examples completed successfully!")


if __name__ == "__main__":
    main()
