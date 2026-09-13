from typing import List
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import find_previous_normal_round
from src.fee_simulator.core.burns import compute_unsuccessful_leader_appeal_burn
from src.fee_simulator.core.bond_computing import compute_appeal_bond


def apply_skip_round(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    """
    Handle skip rounds. These generate no fee events except for burning
    unsuccessful leader appeal bonds from the previous round.
    """
    events = []

    # Check if previous round was an unsuccessful LEADER appeal that needs burning
    if round_index > 0 and round_labels[round_index - 1] in [
        "APPEAL_LEADER_UNSUCCESSFUL",
        "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
    ]:
        # Count actual appeals to find the right appeal index
        appeal_count = sum(
            1 for j in range(round_index) if is_appeal_round(round_labels[j])
        )
        appeal_index = appeal_count - 1

        if appeal_index >= 0 and appeal_index < len(budget.appeals):
            appealant_address = budget.appeals[appeal_index].appealantAddress

            # Find the most recent normal round before the appeal
            normal_round_index = find_previous_normal_round(
                round_index - 1, round_labels
            )
            if normal_round_index is None:
                normal_round_index = round_index - 2  # Default

            # Compute the appeal bond to know the total amount
            appeal_bond = compute_appeal_bond(
                normal_round_index=normal_round_index,
                leader_timeout=budget.leaderTimeout,
                validators_timeout=budget.validatorsTimeout,
                round_labels=round_labels,
                appeal_round_index=round_index - 1,  # The unsuccessful appeal round
                rotations=budget.rotations,
                rotations_used=budget.rotationsUsed,
            )

            # Use the burn computation method to calculate how much to burn
            # Since this is a skip round, no fees were paid from the bond
            burn_amount = compute_unsuccessful_leader_appeal_burn(
                appeal_bond, []  # No fees distributed from bond in skip round
            )

            if burn_amount > 0:
                events.append(
                    FeeEvent(
                        sequence_id=event_sequence.next_id(),
                        address=appealant_address,
                        round_index=round_index,
                        round_label="SKIP_ROUND",
                        role="APPEALANT",
                        vote="NA",
                        hash="0xdefault",
                        cost=0,
                        staked=0,
                        earned=0,
                        slashed=0,
                        burned=burn_amount,
                    )
                )

    return events
