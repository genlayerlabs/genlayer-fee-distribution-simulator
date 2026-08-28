from src.fee_simulator.protocol.appeal_economics import successful_appeal_reward
from typing import List
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
    RoundLabel,
)
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import find_previous_normal_round


def apply_appeal_leader_timeout_successful(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    events = []

    # Find which appeal this is by counting appeals up to this point
    appeal_count = sum(
        1 for i in range(round_index + 1) if is_appeal_round(round_labels[i])
    )
    appeal_index = appeal_count - 1

    if appeal_index < 0 or appeal_index >= len(budget.appeals):
        raise ValueError(
            f"Appeal index {appeal_index} out of bounds for round {round_index}"
        )

    appeal = budget.appeals[appeal_index]
    appealant_address = appeal.appealantAddress

    # Find the most recent normal round before this appeal
    normal_round_index = find_previous_normal_round(round_index, round_labels)
    if normal_round_index is None:
        normal_round_index = round_index - 1  # Default

    appeal_bond = compute_appeal_bond(
        normal_round_index=normal_round_index,
        leader_timeout=budget.leaderTimeout,
        validators_timeout=budget.validatorsTimeout,
        round_labels=round_labels,
        rotations=budget.rotations,
        rotations_used=budget.rotationsUsed,
    )
    events.append(
        FeeEvent(
            sequence_id=event_sequence.next_id(),
            address=appealant_address,
            round_index=round_index,
            round_label="APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
            role="APPEALANT",
            earned=successful_appeal_reward(appeal_bond),
        )
    )
    return events
