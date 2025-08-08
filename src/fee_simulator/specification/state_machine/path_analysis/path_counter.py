"""
Path counting using adjacency matrix method.

This module implements efficient path counting using matrix multiplication,
following the principle of separating the algorithm from the data structure.
"""

from typing import Dict, List, Optional, Set
import numpy as np

from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    Graph,
    NodeName,
    PathConstraints,
    CountingResult,
)


def _build_adjacency_matrix(graph: Graph) -> tuple[np.ndarray, Dict[NodeName, int]]:
    """
    Build adjacency matrix and node index mapping from graph.

    Args:
        graph: The graph structure

    Returns:
        Tuple of (adjacency_matrix, node_to_index_mapping)
    """
    nodes = sorted(graph.keys())
    n = len(nodes)
    node_to_idx = {node: i for i, node in enumerate(nodes)}

    matrix = np.zeros((n, n), dtype=int)
    for i, node in enumerate(nodes):
        for next_node in graph[node]:
            if next_node in node_to_idx:
                j = node_to_idx[next_node]
                matrix[i, j] = 1

    return matrix, node_to_idx


def _count_paths_of_length(
    matrix: np.ndarray, source_idx: int, target_idx: int, length: int
) -> int:
    """
    Count paths of specific length between two nodes.

    Uses the property that A^k[i,j] gives the number of paths
    of length k from node i to node j.
    """
    if length == 0:
        return 1 if source_idx == target_idx else 0

    # Compute matrix^length
    result = np.linalg.matrix_power(matrix, length)
    return int(result[source_idx, target_idx])


def count_paths_between_nodes(
    graph: Graph, constraints: PathConstraints, verbose: bool = False
) -> CountingResult:
    """
    Count all paths between two nodes within length constraints.

    This is a pure function - given the same inputs, it always
    produces the same output with no side effects.

    Args:
        graph: The graph structure
        constraints: Path constraints including source, target, and lengths
        verbose: Whether to print progress information

    Returns:
        CountingResult with total count and distribution by length
    """
    matrix, node_to_idx = _build_adjacency_matrix(graph)

    # Validate nodes exist
    if constraints.source_node not in node_to_idx:
        raise ValueError(f"Source node '{constraints.source_node}' not in graph")
    if constraints.target_node not in node_to_idx:
        raise ValueError(f"Target node '{constraints.target_node}' not in graph")

    source_idx = node_to_idx[constraints.source_node]
    target_idx = node_to_idx[constraints.target_node]

    # Count paths for each valid length
    by_length = {}
    total_count = 0

    # Precompute matrix powers for efficiency
    current_power = np.eye(len(matrix), dtype=int)

    for length in range(1, constraints.max_length + 1):
        current_power = np.dot(current_power, matrix)

        if length >= constraints.min_length:
            count = int(current_power[source_idx, target_idx])
            if count > 0:
                by_length[length] = count
                total_count += count

                if verbose:
                    print(f"Length {length}: {count} paths")

    return CountingResult(count=total_count, by_length=by_length)


def get_reachable_nodes(
    graph: Graph, start_node: NodeName, max_steps: int
) -> Set[NodeName]:
    """
    Find all nodes reachable from start_node within max_steps.

    Useful for understanding graph connectivity.
    """
    matrix, node_to_idx = _build_adjacency_matrix(graph)
    start_idx = node_to_idx[start_node]

    # Sum powers of adjacency matrix up to max_steps
    reachability = np.eye(len(matrix), dtype=bool)
    current = np.eye(len(matrix), dtype=bool)

    for _ in range(max_steps):
        current = np.dot(current, matrix).astype(bool)
        reachability |= current

    # Extract reachable nodes
    idx_to_node = {v: k for k, v in node_to_idx.items()}
    reachable_indices = np.where(reachability[start_idx])[0]

    return {idx_to_node[idx] for idx in reachable_indices}
