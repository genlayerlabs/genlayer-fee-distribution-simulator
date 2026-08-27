"""
Graph data structure for the fee simulator round combinations.
"""

from types import MappingProxyType
from typing import Dict, List, Any

# The dependency graph as pure data
# Using MappingProxyType for immutability
_GRAPH_DATA = {
    "START": [
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "LEADER_RECEIPT_UNDETERMINED",
        "LEADER_RECEIPT_MAJORITY_DISAGREE",
        "LEADER_RECEIPT_MAJORITY_TIMEOUT",
        "LEADER_TIMEOUT",
    ],
    # Normal round outcomes with leader receipt
    "LEADER_RECEIPT_MAJORITY_AGREE": [
        "VALIDATOR_APPEAL_SUCCESSFUL",
        "VALIDATOR_APPEAL_UNSUCCESSFUL",
        "END",
    ],
    "LEADER_RECEIPT_UNDETERMINED": [
        "LEADER_APPEAL_SUCCESSFUL",
        "LEADER_APPEAL_UNSUCCESSFUL",
        "END",
    ],
    "LEADER_RECEIPT_MAJORITY_DISAGREE": [
        "LEADER_APPEAL_SUCCESSFUL",
        "LEADER_APPEAL_UNSUCCESSFUL",
        "END",
    ],
    "LEADER_RECEIPT_MAJORITY_TIMEOUT": [
        "VALIDATOR_APPEAL_SUCCESSFUL",
        "VALIDATOR_APPEAL_UNSUCCESSFUL",
        "END",
    ],
    # Leader timeout
    "LEADER_TIMEOUT": [
        "LEADER_APPEAL_TIMEOUT_SUCCESSFUL",
        "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL",
        "END",
    ],
    # Successful appeals can lead to any round type
    "VALIDATOR_APPEAL_SUCCESSFUL": [
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "LEADER_RECEIPT_UNDETERMINED",
        "LEADER_RECEIPT_MAJORITY_DISAGREE",
        "LEADER_RECEIPT_MAJORITY_TIMEOUT",
        "LEADER_TIMEOUT",
        "END",
    ],
    "LEADER_APPEAL_SUCCESSFUL": [
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "LEADER_RECEIPT_MAJORITY_DISAGREE",
        "LEADER_RECEIPT_MAJORITY_TIMEOUT",
        "LEADER_TIMEOUT",
    ],
    "LEADER_APPEAL_TIMEOUT_SUCCESSFUL": [
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "LEADER_RECEIPT_UNDETERMINED",
        "LEADER_RECEIPT_MAJORITY_DISAGREE",
        "LEADER_RECEIPT_MAJORITY_TIMEOUT",
    ],
    # Unsuccessful appeals have restricted transitions
    "VALIDATOR_APPEAL_UNSUCCESSFUL": [
        "VALIDATOR_APPEAL_SUCCESSFUL",
        "VALIDATOR_APPEAL_UNSUCCESSFUL",
        "END",
    ],
    "LEADER_APPEAL_UNSUCCESSFUL": [
        "LEADER_RECEIPT_UNDETERMINED",
    ],
    "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL": [
        "LEADER_TIMEOUT",
    ],
    # Terminal state
    "END": [],
}


# Expose immutable view of the graph
TRANSACTION_GRAPH: Dict[str, List[str]] = MappingProxyType(_GRAPH_DATA)


def is_protocol_valid_path(path: List[str]) -> bool:
    """Enforce lifecycle rules that need path history, not one graph edge.

    A successful validator-review jury is followed by exactly one terminal
    normal recomputation. That terminal decision ends this appeal ladder and
    cannot itself be appealed again.
    """

    terminal_normal_seen = False
    expect_terminal_normal = False
    for node in path:
        if terminal_normal_seen and node != "END":
            return False
        if expect_terminal_normal:
            if node == "END":
                return True
            if "APPEAL" in node or node == "START":
                return False
            expect_terminal_normal = False
            terminal_normal_seen = True
            continue
        if node == "VALIDATOR_APPEAL_SUCCESSFUL":
            expect_terminal_normal = True
    return True


def get_graph() -> Dict[str, List[str]]:
    """
    Get a copy of the transaction graph.

    Returns a mutable copy for algorithms that need to modify the structure.
    """
    return dict(_GRAPH_DATA)


# --- Node metadata for variant generation ---
# Documents which graph nodes support rotations (leader timeout before final outcome)
# and idle validators. This is the single source of truth for variant expansion.
_NODE_METADATA = {
    "LEADER_RECEIPT_MAJORITY_AGREE": {"rotations": True, "idle": True},
    "LEADER_RECEIPT_MAJORITY_DISAGREE": {"rotations": True, "idle": True},
    "LEADER_RECEIPT_MAJORITY_TIMEOUT": {"rotations": True, "idle": True},
    "LEADER_RECEIPT_UNDETERMINED": {"rotations": True, "idle": True},
    "LEADER_TIMEOUT": {"rotations": True, "idle": False},
}

GRAPH_NODE_METADATA: Dict[str, Dict[str, Any]] = MappingProxyType(_NODE_METADATA)
