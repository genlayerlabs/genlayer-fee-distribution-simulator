"""
Graph data structure for the consensus transaction state machine.

Represents all possible transaction state transitions in the GenLayer
consensus system, derived from the Solidity implementation
(Transactions.sol, Rounds.sol, Appeals.sol, Idleness.sol).

This is a faithful 1:1 translation of the Mermaid diagram in
docs/spec/03-consensus-stages.md. All intermediate/decision nodes
(RotCheck, PendIdle, CommIdle, etc.) are preserved as distinct graph
nodes so that every path through the graph corresponds to a real
execution path in the contracts.

Node types:
  - Transaction states: match the TransactionStatus enum in ITransactions.sol
  - Decision nodes: intermediate branching points (e.g. ROT_CHECK, PEND_IDLE)
  - Processing nodes: represent compound operations (e.g. SLASH_PARTIAL)
"""

from types import MappingProxyType
from typing import Dict, List


_GRAPH_DATA = {
    # =========================================================================
    # MAIN FLOW
    # =========================================================================
    "PENDING": [
        "PROPOSING",  # Activated by activator validator
        "UNDETERMINED",  # Activation fails: no validators found
        "CANCELED",  # User cancel / tx expired (validUntil)
        "PEND_IDLE",  # Idleness: activator timeout
    ],
    "PROPOSING": [
        "COMMITTING",  # Leader proposes valid receipt
        "LEADER_TIMEOUT",  # Leader proposes empty receipt / timeout
        "CANCELED",  # Tx expired (validUntil)
        "LEADER_IDLE",  # Idleness: leader idle
    ],
    "COMMITTING": [
        "LEADER_REVEALING",  # All validators committed
        "COMM_IDLE",  # Idleness: commit timeout
    ],
    "LEADER_REVEALING": [
        "REVEALING",  # Leader reveals vote successfully
        "LEADER_IDLE",  # Idleness: leader reveal timeout
    ],
    "REVEALING": [
        "ACCEPTED",  # Majority agree
        "VALIDATORS_TIMEOUT",  # Majority timeout
        "ROT_CHECK",  # Disagree / no majority
        "ROT_CHECK",  # Det. violation + tribunal (parallel)
        "SLASH_PARTIAL",  # Idleness: reveal timeout
        "REVEAL_RESOLVE",  # Appeal submitted (first slot elapsed)
    ],

    # =========================================================================
    # REVEAL OUTCOME DECISIONS
    # =========================================================================
    "ROT_CHECK": [
        "ROT_ATTEMPT",  # Yes: rotations available & not hanging
        "UNDETERMINED",  # No: no rotations or hanging
    ],
    "ROT_ATTEMPT": [
        "PROPOSING",  # Yes: validators found, rotate leader
        "UNDETERMINED",  # No: no validators found
    ],

    # =========================================================================
    # IDLENESS: PENDING (activator)
    # =========================================================================
    "PEND_IDLE": [
        "PENDING",  # No: not hanging, rotate activator
        "UNDETERMINED",  # Yes: hanging tx
    ],

    # =========================================================================
    # IDLENESS: PROPOSING / LEADER REVEALING (leader)
    # =========================================================================
    "LEADER_IDLE": [
        "PROPOSING",  # No: not hanging, rotate leader
        "UNDETERMINED",  # Yes: hanging tx
    ],

    # =========================================================================
    # IDLENESS: COMMITTING (leader + validators)
    # =========================================================================
    "COMM_IDLE": [
        "UNDETERMINED",  # Hanging / no replacement validators found
        "PROPOSING",  # Leader idle: rotate leader
        "COMMITTING",  # Validators idle: replace & stay
    ],

    # =========================================================================
    # IDLENESS: REVEALING (slash + partial vote)
    # =========================================================================
    "SLASH_PARTIAL": [
        "ACCEPTED",  # Partial vote: majority agree
        "VALIDATORS_TIMEOUT",  # Partial vote: majority timeout
        "ROT_CHECK",  # Partial vote: disagree / no majority
    ],

    # =========================================================================
    # APPEAL ON REVEALING (force resolve first)
    # =========================================================================
    "REVEAL_RESOLVE": [
        "APPEAL_COMMITTING",  # Result: Accepted/VT → validator appeal
        "PROPOSING",  # Result: Undetermined/LT → leader appeal (auto-success)
        "PROPOSING",  # Rotation triggered during resolve
    ],

    # =========================================================================
    # DECIDED STATES
    # =========================================================================
    "ACCEPTED": [
        "APPEAL_COMMITTING",  # Validator appeal submitted
        "FINALIZED",  # Appeal window expires, no appeal
    ],
    "VALIDATORS_TIMEOUT": [
        "APPEAL_COMMITTING",  # Validator appeal submitted
        "FINALIZED",  # Appeal window expires, no appeal
    ],
    "UNDETERMINED": [
        "PROPOSING",  # Leader appeal (auto-success)
        "FINALIZED",  # No appeal
    ],
    "LEADER_TIMEOUT": [
        "PROPOSING",  # Leader appeal (auto-success)
        "FINALIZED",  # No appeal
    ],

    # =========================================================================
    # APPEAL FLOW
    # =========================================================================
    "APPEAL_COMMITTING": [
        "APPEAL_REVEALING",  # All validators committed in appeal round
        "ACOMM_IDLE",  # Idleness: commit timeout
    ],
    "ACOMM_IDLE": [
        "UNDETERMINED",  # Hanging / no replacement validators found
        "PROPOSING",  # Leader idle: rotate leader
        "APPEAL_COMMITTING",  # Validators idle: replace & stay
    ],
    "APPEAL_REVEALING": [
        "PROPOSING",  # Appeal succeeds: new round
        "ACCEPTED",  # Appeal fails: confirms original Accepted
        "VALIDATORS_TIMEOUT",  # Appeal fails: confirms original Validator Timeout
        "UNDETERMINED",  # Appeal fails: no more validators
        "APP_SLASH",  # Idleness: reveal timeout
    ],

    # =========================================================================
    # IDLENESS: APPEAL REVEALING (slash + partial vote)
    # =========================================================================
    "APP_SLASH": [
        "PROPOSING",  # Partial vote: appeal succeeds, new round
        "ACCEPTED",  # Partial vote: fails, was Accepted
        "VALIDATORS_TIMEOUT",  # Partial vote: fails, was Validator Timeout
        "UNDETERMINED",  # Partial vote: fails, no more validators
    ],

    # =========================================================================
    # TERMINAL STATES
    # =========================================================================
    "FINALIZED": [],
    "CANCELED": [],
}


# Expose immutable view of the graph
CONSENSUS_GRAPH: Dict[str, List[str]] = MappingProxyType(_GRAPH_DATA)


def get_graph() -> Dict[str, List[str]]:
    """
    Get a copy of the consensus transaction state graph.

    Returns a mutable copy for algorithms that need to modify the structure.
    """
    return dict(_GRAPH_DATA)
