"""
Convert TRANSITIONS_GRAPH paths to TransactionRoundResults objects.

This module provides the bridge between graph paths and the transaction
data structures used by the fee distribution system.
"""

from typing import List, Dict, Optional, Tuple
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
    """Create votes where majority disagrees.

    The leader cannot vote against its own receipt: on-chain the proposal IS
    the leader's implicit AGREE vote (the contracts derive it from
    leaderRevealVote), so a disagree majority must come entirely from the
    validators — majority_count of them — and the leader ends up non-aligned
    (penalized as a validator while still earning the leader fee).
    """
    votes = {
        addresses[0]: ["LEADER_RECEIPT", "AGREE"],  # Leader (implicit agree)
    }

    # Calculate majority threshold (more than half)
    majority_count = (size // 2) + 1

    # majority_count validators disagree (the leader's implicit AGREE does not
    # contribute to the disagree majority)
    for i in range(1, min(majority_count + 1, size)):
        votes[addresses[i]] = "DISAGREE"

    # Rest of validators split between AGREE and TIMEOUT
    for i in range(majority_count + 1, size):
        if (i - majority_count - 1) % 2 == 0:
            votes[addresses[i]] = "AGREE"
        else:
            votes[addresses[i]] = "TIMEOUT"

    return votes


def create_majority_timeout_votes(
    size: int, addresses: List[str], offset: int = 0
) -> Dict[str, Vote]:
    """Create votes where majority times out.

    As with the disagree case, the leader's receipt is an implicit AGREE vote
    (a leader that itself times out is the LEADER_TIMEOUT path, not a receipt
    round), so the timeout majority must come from majority_count validators
    and the leader ends up non-aligned.
    """
    votes = {
        addresses[0]: ["LEADER_RECEIPT", "AGREE"],  # Leader (implicit agree)
    }

    # Calculate majority threshold (more than half)
    majority_count = (size // 2) + 1

    # majority_count validators time out
    for i in range(1, min(majority_count + 1, size)):
        votes[addresses[i]] = "TIMEOUT"

    # Rest of validators split between AGREE and DISAGREE
    for i in range(majority_count + 1, size):
        if (i - majority_count - 1) % 2 == 0:
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


def create_vote_rotation_votes(
    size: int, addresses: List[str], offset: int = 0
) -> Dict[str, Vote]:
    """Create votes for a vote-based rotation entry: the committee unanimously
    rejects the leader's proposal (majority DISAGREE), rotating the leader.

    Mirrors the on-chain vote-based rotation trigger. In the backward rotation
    loop every disagreeing validator of the entry is aligned with the entry's
    own result and earns its validator fee; the rotated-out leader earns the
    50% compensation and is neither paid a validator fee nor penalized.
    """
    votes = {
        addresses[0]: ["LEADER_RECEIPT", "AGREE"],  # Leader (implicit agree)
    }
    for i in range(1, size):
        votes[addresses[i]] = "DISAGREE"
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
            else:  # TIMEOUT
                # On-chain (Rounds.sol) an appeal against ValidatorsTimeout
                # fails only when the appeal round CONFIRMS the outcome with
                # a timeout majority; a NoMajority composition would make the
                # appeal succeed. Synthesize a genuine confirming majority.
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "TIMEOUT"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "AGREE"

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
    rotation_counts: Optional[Dict[int, int]] = None,
    idle_config: Optional[Dict[int, int]] = None,
    rotation_kind: str = "timeout",
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
        rotation_counts: Optional mapping of round index (0-based, counting only normal
            rounds) to number of leader rotations before the final outcome.
            E.g. {0: 2} means the first normal round has 2 rotations before the final leader.
        rotation_kind: How the intermediate rotations happen — "timeout" (the
            leader never proposes; only the 50% compensation is due) or "vote"
            (the committee unanimously rejects the proposal; the entry's
            aligned validators are paid per the backward rotation loop).
        idle_config: Optional mapping of round index to number of idle validators.
            E.g. {0: 2} means 2 validators in the first round are IDLE.

    Returns:
        Tuple of (TransactionRoundResults, TransactionBudget)
    """
    if sender_address is None:
        sender_address = addresses[-1]
    if appealant_address is None:
        appealant_address = addresses[-2]
    if removed_addresses is None:
        removed_addresses = set()
    if rotation_counts is None:
        rotation_counts = {}
    if idle_config is None:
        idle_config = {}
    if rotation_kind not in ("timeout", "vote"):
        raise ValueError(
            f"rotation_kind must be 'timeout' or 'vote', got {rotation_kind!r}"
        )

    rounds = []
    appeals = []

    # State tracking
    cumulative_active = set()
    next_unused_idx = 0
    previous_leaders = []
    normal_count = 0
    appeal_count = 0
    # Appeals that actually expand the committee (leader/validator vote
    # appeals). Leader-timeout appeals draw no committee on-chain and do not
    # advance the size schedule, so they are excluded from this counter.
    expanding_appeal_count = 0

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

            is_timeout_appeal = "LEADER_APPEAL_TIMEOUT" in node

            if is_timeout_appeal:
                # On-chain a leader-timeout appeal has NO voting committee —
                # it just replaces the leader and re-executes
                # (RoundsCreation.createNewLeaderTimeoutAppealRound). The
                # appeal round keeps only the appellant bookkeeping: NA
                # entries over the appealed round's committee, no fresh
                # draws, nothing new enters the cumulative active set.
                appeal_addresses = (
                    list(rounds[-1].rotations[-1].votes.keys())
                    if rounds and rounds[-1].rotations
                    else []
                )
                # RoundsCreation reverts CanNotAppeal when the timed-out
                # round has <= 1 member: dropping the leader would leave an
                # empty committee for the induced round.
                if len(appeal_addresses) <= 1:
                    raise ValueError(
                        f"CanNotAppeal: leader-timeout appeal at path node {i + 1} "
                        f"targets a round with {len(appeal_addresses)} member(s); "
                        "on-chain the appeal reverts once the committee cannot "
                        "shrink further (RoundsCreation.createNewLeaderTimeoutAppealRound)"
                    )
            else:
                # Calculate appeal size (leader-timeout appeals do not
                # consume a slot in the appeal size schedule)
                base_size = (
                    APPEAL_ROUND_SIZES[expanding_appeal_count]
                    if expanding_appeal_count < len(APPEAL_ROUND_SIZES)
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
            if not is_timeout_appeal:
                expanding_appeal_count += 1

        else:  # Normal round
            previous_node = path[i] if i > 0 else None
            induced_by_timeout_appeal = (
                previous_node is not None and "LEADER_APPEAL_TIMEOUT" in previous_node
            )

            # Calculate required size based on blockchain index
            # After N appeals, the next normal round is at blockchain index 2*N
            if normal_count == 0:
                blockchain_idx = 0
            else:
                # Count how many committee-expanding appeals have occurred.
                # Leader-timeout appeals re-execute with the SAME validator
                # set minus the timed-out leader, so they must not bump the
                # size tier.
                blockchain_idx = 2 * expanding_appeal_count

            size_idx = blockchain_idx // 2
            required_size = (
                NORMAL_ROUND_SIZES[size_idx]
                if size_idx < len(NORMAL_ROUND_SIZES)
                else NORMAL_ROUND_SIZES[-1]
            )

            if induced_by_timeout_appeal:
                # Round induced by a leader-timeout appeal (round + 2
                # on-chain, RoundsCreation.createNewLeaderTimeoutAppealRound):
                # the SAME validator set is kept, the timed-out leader is
                # dropped (order preserved) and the validator at index
                # L % (N-1) of the reduced array becomes the new leader —
                # NO new validators are selected. Chained timeout appeals
                # therefore shrink the committee each time (5 -> 4 -> 3 ...).
                timed_out_committee = list(rounds[-2].rotations[-1].votes.keys())
                leader_idx = 0  # the simulator always seats the leader first
                reduced = (
                    timed_out_committee[:leader_idx]
                    + timed_out_committee[leader_idx + 1 :]
                )
                new_leader_idx = leader_idx % len(reduced)
                # Rotate so the new leader sits at index 0 (the simulator's
                # leader slot) while preserving the on-chain array order.
                normal_addresses = reduced[new_leader_idx:] + reduced[:new_leader_idx]
            elif normal_count == 0:
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

            # Build rotations list for this round
            num_timeout_rotations = rotation_counts.get(normal_count, 0)
            num_idle = idle_config.get(normal_count, 0)
            rotations_list = []

            round_participants = set(normal_addresses)

            if num_timeout_rotations > 0:
                # Create rotation entries before the final outcome. Each entry
                # is led by the committee's current first address; "timeout"
                # entries carry no votes, "vote" entries carry a unanimous
                # rejection.
                make_rotation_votes = (
                    create_vote_rotation_votes
                    if rotation_kind == "vote"
                    else create_leader_timeout_votes
                )
                committee = list(normal_addresses)
                for rot_idx in range(num_timeout_rotations):
                    if not committee:
                        break
                    entry_leader = committee[0]
                    rotation_votes = make_rotation_votes(len(committee), committee)
                    rotations_list.append(Rotation(votes=rotation_votes))
                    previous_leaders.append(entry_leader)

                    # Committee replacement (on-chain RoundsCreation): the
                    # rotated-out leader leaves the committee and a fresh
                    # validator from the pool joins. The rotated-out leader
                    # keeps only the 50% comp — never a final-round vote,
                    # reward or penalty.
                    replacement = None
                    while next_unused_idx < len(addresses):
                        cand = addresses[next_unused_idx]
                        next_unused_idx += 1
                        if cand not in removed_addresses:
                            replacement = cand
                            break
                    committee = [a for a in committee if a != entry_leader]
                    if replacement is not None:
                        committee.append(replacement)
                        round_participants.add(replacement)

                # Final rotation votes over the replaced committee
                final_round = create_normal_round(node, committee)
                rotations_list.append(final_round.rotations[0])
                round_obj = Round(rotations=rotations_list)
                final_committee = committee
            else:
                # No rotations, create a normal single-rotation round
                round_obj = create_normal_round(node, normal_addresses)
                final_committee = normal_addresses

            # Apply idle config: replace some validator votes with IDLE
            if num_idle > 0 and round_obj.rotations:
                last_rot = round_obj.rotations[-1]
                votes = dict(last_rot.votes)
                # Make the last num_idle validators IDLE
                validator_addrs = [
                    addr
                    for addr in votes.keys()
                    if not (
                        isinstance(votes[addr], list)
                        and votes[addr][0] in ["LEADER_RECEIPT", "LEADER_TIMEOUT"]
                    )
                ]
                for idle_idx in range(min(num_idle, len(validator_addrs))):
                    idle_addr = validator_addrs[-(idle_idx + 1)]
                    votes[idle_addr] = "IDLE"
                new_last_rot = Rotation(votes=votes)
                new_rotations = list(round_obj.rotations[:-1]) + [new_last_rot]
                round_obj = Round(rotations=new_rotations)

            rounds.append(round_obj)

            # Update state
            cumulative_active.update(round_participants)
            if final_committee:
                previous_leaders.append(final_committee[0])
            normal_count += 1

            # Track majority for appeals (always from last rotation)
            if round_obj.rotations and round_obj.rotations[-1].votes:
                last_normal_majority = compute_majority(round_obj.rotations[-1].votes)

        # Track the majority outcome of this round (from the final rotation)
        if round_obj.rotations and round_obj.rotations[-1].votes:
            prev_majority = compute_majority(round_obj.rotations[-1].votes)

    # The latest Consensus has two distinct rotation concepts:
    # - feesDistribution.rotations is the funded schedule;
    # - RoundsStorage.rotationsLeft is live runtime capacity.
    # Every normal round is seeded from one transaction-wide capacity clamped
    # to the smallest funded entry. The minimal valid schedule for this path is
    # therefore uniform at the largest number of rotations actually exercised.
    rotations_used = []
    for nc in range(normal_count):
        rotations_used.append(rotation_counts.get(nc, 0))
    initial_rotation_capacity = max(rotations_used, default=0)
    funded_rotations = [initial_rotation_capacity] * normal_count

    budget = TransactionBudget(
        leaderTimeout=leader_timeout,
        validatorsTimeout=validators_timeout,
        appealRounds=appeal_count,
        rotations=funded_rotations,
        rotationsUsed=rotations_used,
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
