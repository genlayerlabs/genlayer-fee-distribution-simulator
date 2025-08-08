"""
Path analysis and statistics computation.
"""

from typing import List, Dict, Set, Tuple
from collections import Counter

from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    Path,
    PathStatistics,
    SPECIAL_NODES,
    APPEAL_PATTERNS,
    OUTCOME_PATTERNS,
)


def _count_appeals_in_path(path: Path) -> int:
    """Count the number of appeal nodes in a path."""
    return sum(1 for node in path if "APPEAL" in node)


def _get_real_nodes(path: Path) -> List[str]:
    """Get nodes excluding special START/END nodes."""
    return [node for node in path if node not in SPECIAL_NODES]


def _extract_patterns_from_path(path: Path, patterns: Set[str]) -> Set[str]:
    """Extract which patterns appear in a path."""
    found_patterns = set()
    for pattern in patterns:
        if any(pattern in node for node in path):
            found_patterns.add(pattern)
    return found_patterns


def analyze_paths(paths: List[Path]) -> PathStatistics:
    """
    Compute comprehensive statistics about a collection of paths.

    This is a pure function that extracts multiple statistics in a
    single pass for efficiency.

    Args:
        paths: Collection of paths to analyze

    Returns:
        PathStatistics containing various metrics
    """
    # Initialize counters
    length_counter = Counter()
    appeal_counter = Counter()
    real_length_counter = Counter()
    pattern_counter = Counter()

    # Combine all patterns we're interested in
    all_patterns = APPEAL_PATTERNS | OUTCOME_PATTERNS | {"LEADER_TIMEOUT"}

    # Single pass through all paths
    for path in paths:
        # Length statistics
        length_counter[len(path)] += 1

        # Real length (excluding START/END)
        real_nodes = _get_real_nodes(path)
        real_length_counter[len(real_nodes)] += 1

        # Appeal statistics
        appeal_count = _count_appeals_in_path(path)
        appeal_counter[appeal_count] += 1

        # Pattern detection
        found_patterns = _extract_patterns_from_path(path, all_patterns)
        pattern_counter.update(found_patterns)

    return PathStatistics(
        total_paths=len(paths),
        length_distribution=dict(length_counter),
        appeal_distribution=dict(appeal_counter),
        real_length_distribution=dict(real_length_counter),
        pattern_frequency=dict(pattern_counter),
    )


def find_extreme_paths(
    paths: List[Path], count: int = 3
) -> Tuple[List[Path], List[Path]]:
    """
    Find the shortest and longest paths.

    Args:
        paths: Collection of paths
        count: Number of shortest/longest to return

    Returns:
        Tuple of (shortest_paths, longest_paths)
    """
    if not paths:
        return [], []

    sorted_by_length = sorted(paths, key=len)
    shortest = sorted_by_length[:count]
    longest = (
        sorted_by_length[-count:]
        if len(sorted_by_length) >= count
        else sorted_by_length
    )

    return shortest, list(reversed(longest))


def group_paths_by_feature(
    paths: List[Path], feature_extractor
) -> Dict[any, List[Path]]:
    """
    Group paths by a custom feature extraction function.

    This is a higher-order function that enables flexible grouping.

    Args:
        paths: Collection of paths
        feature_extractor: Function that extracts a feature from a path

    Returns:
        Dictionary mapping features to lists of paths
    """
    groups = {}
    for path in paths:
        feature = feature_extractor(path)
        if feature not in groups:
            groups[feature] = []
        groups[feature].append(path)
    return groups


def find_paths_with_rare_patterns(
    paths: List[Path], threshold: float = 0.05
) -> List[Tuple[str, List[Path]]]:
    """
    Find paths containing patterns that appear in less than threshold fraction of paths.

    Useful for finding edge cases and unusual paths.
    """
    stats = analyze_paths(paths)
    total = stats.total_paths

    rare_patterns = [
        pattern
        for pattern, count in stats.pattern_frequency.items()
        if count / total < threshold
    ]

    result = []
    for pattern in rare_patterns:
        matching_paths = [p for p in paths if any(pattern in node for node in p)]
        result.append((pattern, matching_paths))

    return sorted(result, key=lambda x: len(x[1]))


def calculate_path_diversity(paths: List[Path]) -> float:
    """
    Calculate a diversity score for the path collection.

    Higher scores indicate more diverse paths.
    """
    if not paths:
        return 0.0

    # Count unique paths
    unique_paths = len(set(tuple(path) for path in paths))

    # Count unique nodes used
    all_nodes = set()
    for path in paths:
        all_nodes.update(path)

    # Diversity is a combination of unique paths and node coverage
    path_diversity = unique_paths / len(paths)
    node_diversity = len(all_nodes) / (len(all_nodes) + 10)  # Normalized

    return (path_diversity + node_diversity) / 2
