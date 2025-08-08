"""
Debug script to understand the difference between matrix counting and DFS generation.
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
)
from collections import defaultdict


def analyze_path_differences():
    """Analyze why the counts differ between methods."""

    constraints = PathConstraints(
        min_length=3, max_length=5, source_node="START", target_node="END"
    )

    # Get counts from both methods
    matrix_result = count_paths_between_nodes(
        TRANSACTION_GRAPH, constraints, verbose=True
    )
    paths = generate_all_paths(TRANSACTION_GRAPH, constraints)

    print(f"\nMatrix count: {matrix_result.count}")
    print(f"DFS count: {len(paths)}")
    print(f"\nMatrix by length: {matrix_result.by_length}")

    # Count DFS paths by length
    dfs_by_length = defaultdict(int)
    for path in paths:
        dfs_by_length[len(path)] += 1

    print(f"DFS by length: {dict(dfs_by_length)}")

    # Find which lengths have discrepancies
    print("\nDiscrepancies by length:")
    for length in sorted(
        set(matrix_result.by_length.keys()) | set(dfs_by_length.keys())
    ):
        matrix_count = matrix_result.by_length.get(length, 0)
        dfs_count = dfs_by_length.get(length, 0)
        if matrix_count != dfs_count:
            print(
                f"  Length {length}: Matrix={matrix_count}, DFS={dfs_count}, Diff={matrix_count - dfs_count}"
            )

    # Let's check if there are any simple cycles in the graph
    print("\nChecking for self-loops and simple cycles:")
    for node, neighbors in TRANSACTION_GRAPH.items():
        if node in neighbors:
            print(f"  Self-loop: {node} -> {node}")

        # Check 2-cycles
        for neighbor in neighbors:
            if neighbor in TRANSACTION_GRAPH and node in TRANSACTION_GRAPH[neighbor]:
                print(f"  2-cycle: {node} <-> {neighbor}")

    # Print some example paths to see patterns
    print("\nExample paths of each length:")
    for length in sorted(dfs_by_length.keys()):
        length_paths = [p for p in paths if len(p) == length]
        print(f"\nLength {length} (showing first 3):")
        for i, path in enumerate(length_paths[:3]):
            print(f"  {' -> '.join(path)}")

    # Check if any path appears multiple times
    path_strings = [" -> ".join(path) for path in paths]
    path_counts = defaultdict(int)
    for ps in path_strings:
        path_counts[ps] += 1

    duplicates = [(p, c) for p, c in path_counts.items() if c > 1]
    if duplicates:
        print("\nDuplicate paths found:")
        for path, count in duplicates[:5]:
            print(f"  {path} (appears {count} times)")
    else:
        print("\nNo duplicate paths found in DFS generation")

    # Try to understand what paths the matrix is counting that DFS isn't
    print("\nAnalyzing graph structure for potential missing paths...")

    # Check nodes that can reach themselves
    from path_counter import get_reachable_nodes

    for node in TRANSACTION_GRAPH:
        reachable = get_reachable_nodes(TRANSACTION_GRAPH, node, max_steps=5)
        if node in reachable and node not in ["START", "END"]:
            print(f"  {node} can reach itself")


if __name__ == "__main__":
    analyze_path_differences()
