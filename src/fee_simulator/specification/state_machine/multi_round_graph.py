"""
Multi-round unrolled consensus graph.

Unrolls the single-round consensus_graph across R rounds (0..max_rounds-1),
creating per-round state copies connected by cross-round transitions.

Round types (normal vs appeal) are NOT tied to round number parity.
Consecutive appeal rounds (chained unsuccessful appeals) and consecutive
normal rounds (leader appeals) are both possible. The round type is
determined by the incoming transition.

Node naming:
  - Per-round nodes: R{round}_{state}  (e.g. R0_PENDING, R3_APPEAL_COMMITTING)
  - Global terminal nodes (no prefix): FINALIZED, CANCELED
"""

from types import MappingProxyType
from typing import Dict, List, Set, Tuple

from .consensus_graph import CONSENSUS_GRAPH

# Default max rounds from FeeManager.sol
DEFAULT_MAX_ROUNDS = 20

# Terminal states (global, not per-round)
TERMINAL_STATES = frozenset({"FINALIZED", "CANCELED"})

# All non-terminal states from consensus_graph.py
ROUND_STATES = frozenset(s for s in CONSENSUS_GRAPH if s not in TERMINAL_STATES)

# Cross-round edges: (source, target) pairs that create a new round.
# When source is at round R, target goes to round R+1.
CROSS_ROUND_EDGES: Set[Tuple[str, str]] = {
    # Appeal submissions from decided states
    ("ACCEPTED", "APPEAL_COMMITTING"),
    ("VALIDATORS_TIMEOUT", "APPEAL_COMMITTING"),
    ("UNDETERMINED", "PROPOSING"),
    ("LEADER_TIMEOUT", "PROPOSING"),
    # Appeal outcomes creating new rounds
    ("APPEAL_REVEALING", "PROPOSING"),
    ("APP_SLASH", "PROPOSING"),
    # Reveal resolve creating new round (validator appeal)
    ("REVEAL_RESOLVE", "APPEAL_COMMITTING"),
}
# Note: REVEAL_RESOLVE -> PROPOSING appears twice in consensus_graph.py:
#   1st occurrence: leader appeal result -> cross-round (R -> R+1_PROPOSING)
#   2nd occurrence: rotation during resolve -> intra-round (R -> R_PROPOSING)
# Both edges coexist in the multi-round graph.

# Terminal edges: (source, target) pairs that go to global terminals
TERMINAL_EDGES: Set[Tuple[str, str]] = {
    ("ACCEPTED", "FINALIZED"),
    ("VALIDATORS_TIMEOUT", "FINALIZED"),
    ("UNDETERMINED", "FINALIZED"),
    ("LEADER_TIMEOUT", "FINALIZED"),
    ("PENDING", "CANCELED"),
    ("PROPOSING", "CANCELED"),
}


def _node_name(round_num: int, state: str) -> str:
    """Create a round-prefixed node name."""
    return f"R{round_num}_{state}"


def build_multi_round_graph(
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> Dict[str, List[str]]:
    """
    Build the unrolled multi-round consensus graph.

    Each round 0..max_rounds-1 gets a full copy of all non-terminal states.
    Cross-round edges connect decided/appeal-outcome states to the next
    round's entry points. At the last round, cross-round edges are
    suppressed (decided states can only reach FINALIZED).

    Args:
        max_rounds: Maximum number of rounds (default 20).

    Returns:
        Adjacency list mapping node names to lists of successor node names.
    """
    graph: Dict[str, List[str]] = {}

    for r in range(max_rounds):
        is_last = r == max_rounds - 1

        # Initialize all round-state nodes
        for state in ROUND_STATES:
            graph[_node_name(r, state)] = []

        # Process each edge from the single-round graph
        for source, targets in CONSENSUS_GRAPH.items():
            if source in TERMINAL_STATES:
                continue

            src_node = _node_name(r, source)

            # Track how many times we've seen each target for this source,
            # needed for the REVEAL_RESOLVE -> PROPOSING dual-edge case.
            target_seen_count: Dict[str, int] = {}

            for target in targets:
                count = target_seen_count.get(target, 0)
                target_seen_count[target] = count + 1

                if target in TERMINAL_STATES:
                    # Terminal edge -> global node
                    graph[src_node].append(target)

                elif source == "REVEAL_RESOLVE" and target == "PROPOSING":
                    # Special dual-edge case:
                    #   1st PROPOSING (count==0): cross-round (leader appeal)
                    #   2nd PROPOSING (count==1): intra-round (rotation)
                    if count == 0:
                        # Cross-round: leader appeal result
                        if not is_last:
                            graph[src_node].append(_node_name(r + 1, target))
                    else:
                        # Intra-round: rotation during resolve
                        graph[src_node].append(_node_name(r, target))

                elif (source, target) in CROSS_ROUND_EDGES:
                    # Cross-round edge -> next round
                    if not is_last:
                        graph[src_node].append(_node_name(r + 1, target))

                else:
                    # Intra-round edge -> same round
                    graph[src_node].append(_node_name(r, target))

    # Add global terminal nodes
    graph["FINALIZED"] = []
    graph["CANCELED"] = []

    return graph


# Pre-built default graph (immutable)
MULTI_ROUND_GRAPH: Dict[str, List[str]] = MappingProxyType(
    build_multi_round_graph()
)


def get_multi_round_graph(
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> Dict[str, List[str]]:
    """
    Get a mutable copy of the multi-round graph.

    Args:
        max_rounds: Maximum number of rounds (default 20).

    Returns:
        Mutable adjacency list for the unrolled graph.
    """
    return build_multi_round_graph(max_rounds)
