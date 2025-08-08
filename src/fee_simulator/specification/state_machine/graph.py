"""
Graph data structure for the fee simulator round combinations.
"""

from types import MappingProxyType
from typing import Dict, List


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


def get_graph() -> Dict[str, List[str]]:
    """
    Get a copy of the transaction graph.

    Returns a mutable copy for algorithms that need to modify the structure.
    """
    return dict(_GRAPH_DATA)
