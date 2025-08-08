"""
Path generation using depth-first search.

This module generates actual path sequences, complementing the counting
approach with concrete path enumeration.

IMPORTANT: Path length is measured in edges (transitions between nodes),
not in the number of nodes. A path with n nodes has n-1 edges.
This matches the adjacency matrix counting method.
"""

from typing import List, Set, Generator, Dict

from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    Graph,
    NodeName,
    Path,
    PathConstraints,
)


def _is_valid_path_length(path: Path, constraints: PathConstraints) -> bool:
    """Check if path length is within constraints.

    Length is measured in edges (transitions), not nodes.
    A path with n nodes has n-1 edges.
    """
    edge_count = len(path) - 1
    return constraints.min_length <= edge_count <= constraints.max_length


def _depth_first_search(
    graph: Graph,
    current_node: NodeName,
    target_node: NodeName,
    current_path: Path,
    constraints: PathConstraints,
) -> Generator[Path, None, None]:
    """
    Generator that yields all valid paths to target using DFS.

    This version allows cycles - nodes can be revisited.
    Length is measured in edges (transitions between nodes).
    """
    # Current edge count
    edge_count = len(current_path) - 1

    # Check if we've reached the target
    if current_node == target_node:
        if constraints.min_length <= edge_count <= constraints.max_length:
            yield current_path[:]
        # Don't return here! We might be able to leave and come back
        # Only return if we've hit max edges
        if edge_count >= constraints.max_length:
            return

    # Stop if path already has max edges
    if edge_count >= constraints.max_length:
        return

    # Explore all neighbors (allowing revisits)
    for next_node in graph.get(current_node, []):
        current_path.append(next_node)

        yield from _depth_first_search(
            graph, next_node, target_node, current_path, constraints
        )

        current_path.pop()


def generate_all_paths(graph: Graph, constraints: PathConstraints) -> List[Path]:
    """
    Generate all paths satisfying the given constraints.

    This function allows cycles - nodes can be revisited within paths.

    Args:
        graph: The graph structure
        constraints: Path constraints

    Returns:
        List of all valid paths (including those with cycles)
    """
    # Initialize DFS from source
    current_path = [constraints.source_node]

    # Collect all paths from generator
    all_paths = list(
        _depth_first_search(
            graph,
            constraints.source_node,
            constraints.target_node,
            current_path,
            constraints,
        )
    )

    return all_paths


def generate_paths_lazy(
    graph: Graph, constraints: PathConstraints
) -> Generator[Path, None, None]:
    """
    Lazily generate paths satisfying the given constraints.

    Use this when you don't need all paths in memory at once.
    This version allows cycles.

    Args:
        graph: The graph structure
        constraints: Path constraints

    Yields:
        Valid paths one at a time
    """
    current_path = [constraints.source_node]

    yield from _depth_first_search(
        graph,
        constraints.source_node,
        constraints.target_node,
        current_path,
        constraints,
    )


def generate_simple_paths(graph: Graph, constraints: PathConstraints) -> List[Path]:
    """
    Generate only simple paths (no repeated nodes) satisfying the given constraints.

    This is the old behavior for cases where you don't want cycles.
    Length is measured in edges (transitions), not nodes.

    Args:
        graph: The graph structure
        constraints: Path constraints

    Returns:
        List of simple paths (no cycles)
    """

    def _dfs_simple(
        current_node: NodeName,
        target_node: NodeName,
        current_path: Path,
        visited: Set[NodeName],
    ) -> Generator[Path, None, None]:
        """DFS that prevents revisiting nodes."""
        edge_count = len(current_path) - 1

        if current_node == target_node:
            if constraints.min_length <= edge_count <= constraints.max_length:
                yield current_path[:]
            return

        if edge_count >= constraints.max_length:
            return

        for next_node in graph.get(current_node, []):
            if next_node not in visited:
                visited.add(next_node)
                current_path.append(next_node)

                yield from _dfs_simple(next_node, target_node, current_path, visited)

                current_path.pop()
                visited.remove(next_node)

    # Initialize DFS from source
    visited = {constraints.source_node}
    current_path = [constraints.source_node]

    return list(
        _dfs_simple(
            constraints.source_node,
            constraints.target_node,
            current_path,
            visited,
        )
    )


def count_paths_by_length(paths: List[Path]) -> Dict[int, int]:
    """
    Group paths by their length (measured in edges).

    Simple, pure function for categorizing paths.
    """
    length_counts = {}
    for path in paths:
        edge_count = len(path) - 1  # Count edges, not nodes
        length_counts[edge_count] = length_counts.get(edge_count, 0) + 1
    return length_counts


def filter_paths_containing_pattern(paths: List[Path], pattern: str) -> List[Path]:
    """
    Filter paths that contain a specific pattern.

    Pure function - no side effects.
    """
    return [path for path in paths if any(pattern in node for node in path)]


def get_unique_nodes_from_paths(paths: List[Path]) -> Set[NodeName]:
    """Extract all unique nodes appearing in any path."""
    return {node for path in paths for node in path}


def path_edge_count(path: Path) -> int:
    """Get the number of edges in a path (transitions between nodes)."""
    return len(path) - 1


def path_node_count(path: Path) -> int:
    """Get the number of nodes in a path."""
    return len(path)
