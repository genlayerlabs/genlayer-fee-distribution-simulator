from typing import Callable, Dict, List

from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.core.majority import (
    compute_majority,
    normalize_vote,
    who_is_in_vote_majority,
)
from src.fee_simulator.protocol.constants import PENALTY_REWARD_COEFFICIENT

from src.fee_simulator.core.round_fee_distribution import (
    apply_normal_round,
    apply_appeal_leader_timeout_successful,
    apply_appeal_leader_successful,
    apply_appeal_leader_unsuccessful,
    apply_appeal_leader_timeout_unsuccessful,
    apply_appeal_validator_successful,
    apply_appeal_validator_unsuccessful,
    apply_leader_timeout_50_percent,
    apply_split_previous_appeal_bond,
    apply_leader_timeout_50_previous_appeal_bond,
    apply_leader_timeout_150_previous_normal_round,
    apply_equal_split,
)
from src.fee_simulator.core.round_fee_distribution.skip_round import apply_skip_round

FeeTransformer = Callable[
    [TransactionRoundResults, int, TransactionBudget, EventSequence, List[RoundLabel]],
    List[FeeEvent],
]

FEE_RULES: Dict[RoundLabel, FeeTransformer] = {
    "NORMAL_ROUND": apply_normal_round,
    "EMPTY_ROUND": lambda r, i, b, s, l: [],
    "SKIP_ROUND": apply_skip_round,
    "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL": apply_appeal_leader_timeout_unsuccessful,
    "APPEAL_LEADER_TIMEOUT_SUCCESSFUL": apply_appeal_leader_timeout_successful,
    "APPEAL_LEADER_SUCCESSFUL": apply_appeal_leader_successful,
    "APPEAL_LEADER_UNSUCCESSFUL": apply_appeal_leader_unsuccessful,
    "APPEAL_VALIDATOR_SUCCESSFUL": apply_appeal_validator_successful,
    "APPEAL_VALIDATOR_UNSUCCESSFUL": apply_appeal_validator_unsuccessful,
    "LEADER_TIMEOUT_50_PERCENT": apply_leader_timeout_50_percent,
    "SPLIT_PREVIOUS_APPEAL_BOND": apply_split_previous_appeal_bond,
    "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND": apply_leader_timeout_50_previous_appeal_bond,
    "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND": apply_leader_timeout_150_previous_normal_round,
    "EQUAL_SPLIT": apply_equal_split,
}


# Round labels whose prior rotation entries are paid out, mirroring the
# contract's backward rotation loop (FeesProcessor.processFeesForTx sets
# performRotationCheck only for NORMAL_REWARDS_ROUND and
# LEADER_TIMEOUT_50_PERCENT). Other round types ignore prior rotations.
ROTATION_PAYING_LABELS = frozenset(["NORMAL_ROUND", "LEADER_TIMEOUT_50_PERCENT"])


def distribute_rotation_entry(
    round_index: int,
    rotation_index: int,
    votes: Dict,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_label: RoundLabel,
) -> List[FeeEvent]:
    """
    Distribute fees for an intermediate rotation entry within a round,
    mirroring the contract's backward rotation loop:

    - The rotated-out leader gets 50% of leaderTimeout (no validator fee,
      no penalty — skipLeader semantics).
    - Validators aligned with the entry's own majority earn validatorsTimeout;
      non-aligned validators are penalized.
    - Timeout rotations (no vote majority) pay only the rotated-out leader.
    """
    events = []
    first_addr = next(iter(votes.keys()), None)
    if not first_addr:
        return events

    events.append(
        FeeEvent(
            sequence_id=event_sequence.next_id(),
            address=first_addr,
            round_index=round_index,
            round_label=round_label,
            role="LEADER",
            vote=normalize_vote(votes[first_addr]),
            hash="0xdefault",
            cost=0,
            staked=0,
            earned=int(budget.leaderTimeout / 2),
            slashed=0,
            burned=0,
        )
    )

    # Vote-based rotation (e.g. proposal rejected): pay the entry's aligned
    # validators, penalize non-aligned ones. The rotated-out leader is
    # excluded from both (contract: skipLeader=true in the backward loop).
    majority = compute_majority(votes)
    if majority != "UNDETERMINED":
        majority_addresses, minority_addresses = who_is_in_vote_majority(
            votes, majority
        )
        for addr in majority_addresses:
            if addr == first_addr:
                continue
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label=round_label,
                    role="VALIDATOR",
                    vote=normalize_vote(votes[addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=budget.validatorsTimeout,
                    slashed=0,
                    burned=0,
                )
            )
        for addr in minority_addresses:
            if addr == first_addr:
                continue
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label=round_label,
                    role="VALIDATOR",
                    vote=normalize_vote(votes[addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=0,
                    slashed=0,
                    burned=PENALTY_REWARD_COEFFICIENT * budget.validatorsTimeout,
                )
            )
    return events


def distribute_round(
    transaction_results: TransactionRoundResults,
    round_index: int,
    label: RoundLabel,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    """
    Distribute fees for a single round based on its label, generating FeeEvent instances.

    If the round has multiple rotations (leader timeouts before final outcome),
    intermediate rotations are processed first: each timed-out leader gets 50% of leaderTimeout.
    Then the final rotation is processed using the standard fee rules.
    """
    events = []
    round_obj = transaction_results.rounds[round_index]

    # Process intermediate rotation entries (all except the last), only for
    # round types that pay their prior rotations (mirrors the contract's
    # performRotationCheck flag)
    if len(round_obj.rotations) > 1 and label in ROTATION_PAYING_LABELS:
        for rot_idx in range(len(round_obj.rotations) - 1):
            rotation_events = distribute_rotation_entry(
                round_index=round_index,
                rotation_index=rot_idx,
                votes=round_obj.rotations[rot_idx].votes,
                budget=budget,
                event_sequence=event_sequence,
                round_label=label,
            )
            events.extend(rotation_events)

    # Process the final rotation using the standard fee rules
    transformer = FEE_RULES.get(label, lambda r, i, b, s, l: [])
    events.extend(
        transformer(
            transaction_results, round_index, budget, event_sequence, round_labels
        )
    )
    return events
