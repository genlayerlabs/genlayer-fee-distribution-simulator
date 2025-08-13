"""
Convert TRANSITIONS_GRAPH paths to TransactionRoundResults objects.

This module provides the bridge between graph paths and the transaction
data structures used by the fee distribution system.
"""

from typing import List, Dict, Tuple
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    Round,
    Rotation,
    Appeal,
)
from src.fee_simulator.protocol.types import Vote
from src.fee_simulator.protocol.constants import NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES


def is_appeal_node(node: str) -> bool:
    """Check if a node represents an appeal round."""
    return any(
        appeal_type in node for appeal_type in ["VALIDATOR_APPEAL", "LEADER_APPEAL"]
    )


def create_majority_agree_votes(
    size: int, addresses: List[str], offset: int = 0
) -> Dict[str, Vote]:
    """Create votes where majority agrees."""
    votes = {
        addresses[0]: ["LEADER_RECEIPT", "AGREE"],  # Leader
    }

    # Calculate majority threshold (more than half)
    majority_count = (size // 2) + 1

    # First majority_count-1 validators agree (we already have leader agreeing)
    for i in range(1, min(majority_count, size)):
        votes[addresses[i]] = "AGREE"

    # Rest of validators split between DISAGREE and TIMEOUT
    for i in range(majority_count, size):
        if (i - majority_count) % 2 == 0:
            votes[addresses[i]] = "DISAGREE"
        else:
            votes[addresses[i]] = "TIMEOUT"

    return votes


def create_majority_disagree_votes(
    size: int, addresses: List[str], offset: int = 0
) -> Dict[str, Vote]:
    """Create votes where majority disagrees."""
    votes = {
        addresses[0]: ["LEADER_RECEIPT", "DISAGREE"],  # Leader
    }

    # Calculate majority threshold (more than half)
    majority_count = (size // 2) + 1

    # First majority_count-1 validators disagree (we already have leader disagreeing)
    for i in range(1, min(majority_count, size)):
        votes[addresses[i]] = "DISAGREE"

    # Rest of validators split between AGREE and TIMEOUT
    for i in range(majority_count, size):
        if (i - majority_count) % 2 == 0:
            votes[addresses[i]] = "AGREE"
        else:
            votes[addresses[i]] = "TIMEOUT"

    return votes


def create_majority_timeout_votes(
    size: int, addresses: List[str], offset: int = 0
) -> Dict[str, Vote]:
    """Create votes where majority times out."""
    votes = {
        addresses[0]: ["LEADER_RECEIPT", "TIMEOUT"],  # Leader
    }

    # Calculate majority threshold (more than half)
    majority_count = (size // 2) + 1

    # First majority_count-1 validators timeout (we already have leader timing out)
    for i in range(1, min(majority_count, size)):
        votes[addresses[i]] = "TIMEOUT"

    # Rest of validators split between AGREE and DISAGREE
    for i in range(majority_count, size):
        if (i - majority_count) % 2 == 0:
            votes[addresses[i]] = "AGREE"
        else:
            votes[addresses[i]] = "DISAGREE"

    return votes


def create_undetermined_votes(
    size: int, addresses: List[str], offset: int = 0
) -> Dict[str, Vote]:
    """Create votes with no clear majority (undetermined) - 1/3 agree, 1/3 disagree, 1/3 timeout."""
    votes = {
        addresses[0]: ["LEADER_RECEIPT", "AGREE"],  # Leader
    }

    # Calculate thirds for validators (size - 1 because we exclude the leader)
    num_validators = size - 1
    agree_count = num_validators // 3
    disagree_count = num_validators // 3
    # Remaining validators get TIMEOUT
    timeout_count = num_validators - agree_count - disagree_count

    # Assign votes
    validator_idx = 1

    # Agree votes
    for _ in range(agree_count):
        votes[addresses[validator_idx]] = "AGREE"
        validator_idx += 1

    # Disagree votes
    for _ in range(disagree_count):
        votes[addresses[validator_idx]] = "DISAGREE"
        validator_idx += 1

    # Timeout votes (remaining)
    for _ in range(timeout_count):
        votes[addresses[validator_idx]] = "TIMEOUT"
        validator_idx += 1

    return votes


def create_leader_timeout_votes(
    size: int, addresses: List[str], offset: int = 0
) -> Dict[str, Vote]:
    """Create votes where leader times out."""
    votes = {
        addresses[0]: ["LEADER_TIMEOUT", "NA"],
    }

    for i in range(1, size):
        votes[addresses[i]] = "NA"
    return votes


def create_appeal_votes(
    node: str,
    size: int,
    addresses: List[str],
    offset: int = 0,
    prev_majority: str = None,
) -> Dict[str, Vote]:
    """Create votes for an appeal round based on the node type and previous round context."""
    votes = {}

    # Determine if this is a leader appeal or validator appeal
    is_leader_appeal = "LEADER_APPEAL" in node

    if is_leader_appeal:
        # Leader appeals: All participants get NA votes
        for i in range(size):
            votes[addresses[offset + i]] = "NA"

        # Determine success/failure based on node name and create appropriate majority
        if "SUCCESSFUL" in node and "UNSUCCESSFUL" not in node:
            # Successful leader appeal - create a clear majority (not undetermined/disagree)
            majority_count = (size // 2) + 1
            # Create majority AGREE
            for i in range(majority_count):
                votes[addresses[offset + i]] = (
                    "NA"  # These will be counted as effective AGREE
                )
        else:
            # Unsuccessful leader appeal - maintain undetermined/disagree state
            # Equal distribution ensures no clear majority
            pass  # Already set all to NA
    else:
        # Validator appeals: Validators are appealing the majority decision
        # The success/failure depends on whether appeal changes the outcome

        if "SUCCESSFUL" in node and "UNSUCCESSFUL" not in node:
            # Successful appeal means the outcome changes
            # If previous was AGREE, appeal needs majority DISAGREE/TIMEOUT
            # If previous was DISAGREE, appeal needs majority AGREE
            # If previous was TIMEOUT, appeal needs majority AGREE/DISAGREE
            majority_count = (size // 2) + 1

            if prev_majority == "AGREE":
                # Need majority to disagree or timeout
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "DISAGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "AGREE"
            elif prev_majority == "DISAGREE":
                # Need majority to agree
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "AGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "DISAGREE"
            else:  # TIMEOUT or UNDETERMINED
                # Default to majority disagree
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "DISAGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "AGREE"
        else:
            # Unsuccessful appeal means the outcome stays the same
            # Appeal majority should match previous majority
            majority_count = (size // 2) + 1

            if prev_majority == "AGREE":
                # Majority agrees (same as before)
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "AGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "DISAGREE"
            elif prev_majority == "DISAGREE":
                # Majority disagrees (same as before)
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "DISAGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "AGREE"
            else:  # TIMEOUT or UNDETERMINED
                # For unsuccessful validator appeal after undetermined, maintain undetermined
                # Create equal split to ensure no clear majority
                third = size // 3
                for i in range(third):
                    votes[addresses[offset + i]] = "AGREE"
                for i in range(third, 2 * third):
                    votes[addresses[offset + i]] = "DISAGREE"
                for i in range(2 * third, size):
                    votes[addresses[offset + i]] = "TIMEOUT"

    return votes


def create_normal_round(node: str, addresses: List[str]) -> Round:
    """Create a normal round based on the node type."""
    # Parse node type to determine votes
    if node == "LEADER_RECEIPT_MAJORITY_AGREE":
        votes = create_majority_agree_votes(len(addresses), addresses)
    elif node == "LEADER_RECEIPT_MAJORITY_DISAGREE":
        votes = create_majority_disagree_votes(len(addresses), addresses)
    elif node == "LEADER_RECEIPT_MAJORITY_TIMEOUT":
        votes = create_majority_timeout_votes(len(addresses), addresses)
    elif node == "LEADER_RECEIPT_UNDETERMINED":
        votes = create_undetermined_votes(len(addresses), addresses)
    elif node == "LEADER_TIMEOUT":
        votes = create_leader_timeout_votes(len(addresses), addresses)
    else:
        # Default case
        votes = create_undetermined_votes(len(addresses), addresses)

    return Round(rotations=[Rotation(votes=votes)])


def create_appeal_round(
    node: str, addresses: List[str], prev_majority: str = None
) -> Round:
    """Create an appeal round based on the node type."""
    votes = create_appeal_votes(node, len(addresses), addresses, 0, prev_majority)
    return Round(rotations=[Rotation(votes=votes)])


def path_to_transaction_results(
    path: List[str],
    addresses: List[str],
    sender_address: str = None,
    appealant_address: str = None,
    leader_timeout: int = 100,
    validators_timeout: int = 200,
    removed_addresses: set = None,
) -> Tuple[TransactionRoundResults, TransactionBudget]:
    """
    Convert a TRANSITIONS_GRAPH path to TransactionRoundResults and TransactionBudget.

    Args:
        path: List of node names from TRANSITIONS_GRAPH
        addresses: Pool of addresses to use for participants
        sender_address: Address of the transaction sender (default: addresses[-1])
        appealant_address: Address of the appealant (default: addresses[-2])
        leader_timeout: Leader timeout value
        validators_timeout: Validators timeout value
        removed_addresses: Set of addresses that have been slashed/removed

    Returns:
        Tuple of (TransactionRoundResults, TransactionBudget)
    """
    if sender_address is None:
        sender_address = addresses[-1]
    if appealant_address is None:
        appealant_address = addresses[-2]
    if removed_addresses is None:
        removed_addresses = set()

    rounds = []
    appeals = []

    # State tracking
    cumulative_active = set()
    next_unused_idx = 0
    previous_leaders = []
    normal_count = 0
    appeal_count = 0

    # For tracking majorities
    prev_majority = None
    last_normal_majority = None

    # Import compute_majority for tracking round majorities
    from src.fee_simulator.core.majority import compute_majority

    # Skip START and END nodes
    for i, node in enumerate(path[1:-1]):
        if is_appeal_node(node):
            # Determine if previous was unsuccessful appeal
            # Note: path[i] is the previous node because we're iterating path[1:-1]
            # so path[0] is START, path[i] is the node before current, path[i+1] is current
            previous_node = path[i] if i > 0 else None
            prev_was_unsuccessful = (
                previous_node is not None
                and is_appeal_node(previous_node)
                and "UNSUCCESSFUL" in previous_node
            )

            # Calculate appeal size
            base_size = (
                APPEAL_ROUND_SIZES[appeal_count]
                if appeal_count < len(APPEAL_ROUND_SIZES)
                else APPEAL_ROUND_SIZES[-1]
            )
            required_size = base_size - 2 if prev_was_unsuccessful else base_size

            # Pull new addresses for appeal
            appeal_addresses = []
            while len(appeal_addresses) < required_size and next_unused_idx < len(
                addresses
            ):
                addr = addresses[next_unused_idx]
                next_unused_idx += 1
                if addr not in removed_addresses:
                    appeal_addresses.append(addr)

            # For validator appeals, use the last normal round's majority as context
            context_majority = (
                last_normal_majority if "VALIDATOR_APPEAL" in node else prev_majority
            )

            # Create appeal round
            round_obj = create_appeal_round(node, appeal_addresses, context_majority)
            rounds.append(round_obj)
            appeals.append(Appeal(appealantAddress=appealant_address))

            # Update state
            cumulative_active.update(appeal_addresses)
            appeal_count += 1

        else:  # Normal round
            # Calculate required size based on blockchain index
            # After N appeals, the next normal round is at blockchain index 2*N
            if normal_count == 0:
                blockchain_idx = 0
            else:
                # Count how many appeals have occurred
                blockchain_idx = 2 * appeal_count

            size_idx = blockchain_idx // 2
            required_size = (
                NORMAL_ROUND_SIZES[size_idx]
                if size_idx < len(NORMAL_ROUND_SIZES)
                else NORMAL_ROUND_SIZES[-1]
            )

            if normal_count == 0:
                # First normal round: pull addresses from start
                normal_addresses = []
                while len(normal_addresses) < required_size and next_unused_idx < len(
                    addresses
                ):
                    addr = addresses[next_unused_idx]
                    next_unused_idx += 1
                    if addr not in removed_addresses:
                        normal_addresses.append(addr)
            else:
                # Subsequent normal rounds: use cumulative minus previous leaders
                available = (
                    cumulative_active - set(previous_leaders) - removed_addresses
                )
                sorted_available = sorted(list(available))

                if len(sorted_available) >= required_size:
                    normal_addresses = sorted_available[:required_size]
                else:
                    # Need more addresses
                    normal_addresses = sorted_available
                    needed = required_size - len(normal_addresses)

                    # Pull new addresses
                    while needed > 0 and next_unused_idx < len(addresses):
                        addr = addresses[next_unused_idx]
                        next_unused_idx += 1
                        if addr not in removed_addresses:
                            normal_addresses.append(addr)
                            needed -= 1

                    # Sort to maintain order
                    normal_addresses.sort()

            # Create normal round
            round_obj = create_normal_round(node, normal_addresses)
            rounds.append(round_obj)

            # Update state
            cumulative_active.update(normal_addresses)
            if normal_addresses:
                previous_leaders.append(normal_addresses[0])
            normal_count += 1

            # Track majority for appeals
            if round_obj.rotations and round_obj.rotations[0].votes:
                last_normal_majority = compute_majority(round_obj.rotations[0].votes)

        # Track the majority outcome of this round
        if round_obj.rotations and round_obj.rotations[0].votes:
            prev_majority = compute_majority(round_obj.rotations[0].votes)

    # Create budget
    budget = TransactionBudget(
        leaderTimeout=leader_timeout,
        validatorsTimeout=validators_timeout,
        appealRounds=appeal_count,
        rotations=[0] * normal_count,
        senderAddress=sender_address,
        appeals=appeals,
        staking_distribution="constant",
    )

    return TransactionRoundResults(rounds=rounds), budget


def node_to_expected_label(node: str) -> str:
    """
    Map a graph node to its expected round label.

    This is useful for testing to verify that round_labeling produces
    the expected labels for a given path.
    """
    # Normal rounds
    if node in [
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "LEADER_RECEIPT_MAJORITY_DISAGREE",
        "LEADER_RECEIPT_MAJORITY_TIMEOUT",
        "LEADER_RECEIPT_UNDETERMINED",
    ]:
        return "NORMAL_ROUND"
    elif node == "LEADER_TIMEOUT":
        return "LEADER_TIMEOUT"

    # Appeal rounds - the node name directly maps to the label
    elif node == "VALIDATOR_APPEAL_SUCCESSFUL":
        return "APPEAL_VALIDATOR_SUCCESSFUL"
    elif node == "VALIDATOR_APPEAL_UNSUCCESSFUL":
        return "APPEAL_VALIDATOR_UNSUCCESSFUL"
    elif node == "LEADER_APPEAL_SUCCESSFUL":
        return "APPEAL_LEADER_SUCCESSFUL"
    elif node == "LEADER_APPEAL_UNSUCCESSFUL":
        return "APPEAL_LEADER_UNSUCCESSFUL"
    elif node == "LEADER_APPEAL_TIMEOUT_SUCCESSFUL":
        return "APPEAL_LEADER_TIMEOUT_SUCCESSFUL"
    elif node == "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL":
        return "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL"

    return "UNKNOWN"
