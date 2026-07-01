from typing import List
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
    RoundLabel,
)
from src.fee_simulator.core.majority import normalize_vote
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import find_previous_normal_round
from src.fee_simulator.core.burns import compute_unsuccessful_leader_appeal_burn


def apply_leader_timeout_50_previous_appeal_bond(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    events = []
    round = transaction_results.rounds[round_index]
    if not round.rotations or not budget.appeals or round_index < 1:
        return events

    votes = round.rotations[-1].votes
    sender_address = budget.senderAddress

    # Find the most recent normal round before the previous round
    # This is used to compute the appeal bond from the previous appeal
    normal_round_index = find_previous_normal_round(round_index - 1, round_labels)
    if normal_round_index is None:
        normal_round_index = round_index - 2  # Default

    appeal_bond = compute_appeal_bond(
        normal_round_index,
        budget.leaderTimeout,
        budget.validatorsTimeout,
        round_labels=round_labels,
        appeal_round_index=round_index - 1,
        rotations=budget.rotations,
    )

    # Award half the appeal bond to the leader
    first_addr = next(iter(votes.keys()), None)
    if first_addr:
        events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=first_addr,
                round_index=round_index,
                round_label="LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
                role="LEADER",
                vote=normalize_vote(votes[first_addr]),
                hash="0xdefault",
                cost=0,
                staked=0,
                earned=budget.leaderTimeout * 0.5,
                slashed=0,
                burned=0,
            )
        )

    # Check if previous round was an unsuccessful leader appeal
    # If so, we need to burn the remaining appeal bond
    if round_index > 0 and round_labels[round_index - 1] in [
        "APPEAL_LEADER_UNSUCCESSFUL",
        "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
    ]:
        # The appeal bond amount is the same we already computed above
        # Calculate how much to burn
        burn_amount = compute_unsuccessful_leader_appeal_burn(
            appeal_bond, events  # Only current round events
        )
        # Find which appeal this was by counting appeals up to the previous round
        appeal_count = sum(
            1 for j in range(round_index) if is_appeal_round(round_labels[j])
        )
        appeal_index = appeal_count - 1

        if appeal_index < 0 or appeal_index >= len(budget.appeals):
            raise ValueError(
                f"Appeal index {appeal_index} out of bounds for round {round_index}"
            )

        appealant_address = budget.appeals[appeal_index].appealantAddress
        if burn_amount > 0:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=appealant_address,
                    round_index=round_index,
                    round_label="LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
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
