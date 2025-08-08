from typing import List, Dict, NamedTuple


# Type aliases for clarity
NodeName = str
Path = List[NodeName]
Graph = Dict[NodeName, List[NodeName]]


class PathConstraints(NamedTuple):
    """Immutable constraints for path generation."""

    min_length: int
    max_length: int
    source_node: NodeName = "START"
    target_node: NodeName = "END"
    max_appeals: int = 16


class PathStatistics(NamedTuple):
    """Statistics about a collection of paths."""

    total_paths: int
    length_distribution: Dict[int, int]
    appeal_distribution: Dict[int, int]
    real_length_distribution: Dict[int, int]
    pattern_frequency: Dict[str, int]


class CountingResult(NamedTuple):
    """Result of path counting operations."""

    count: int
    by_length: Dict[int, int]


# Constants that define the problem domain
SPECIAL_NODES = frozenset(["START", "END"])
APPEAL_PATTERNS = frozenset(
    [
        "LEADER_APPEAL_SUCCESSFUL",
        "LEADER_APPEAL_UNSUCCESSFUL",
        "VALIDATOR_APPEAL_SUCCESSFUL",
        "VALIDATOR_APPEAL_UNSUCCESSFUL",
        "LEADER_APPEAL_TIMEOUT_SUCCESSFUL",
        "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL",
    ]
)
OUTCOME_PATTERNS = frozenset(
    [
        "MAJORITY_AGREE",
        "MAJORITY_DISAGREE",
        "UNDETERMINED",
        "MAJORITY_TIMEOUT",
        "LEADER_TIMEOUT",
    ]
)
