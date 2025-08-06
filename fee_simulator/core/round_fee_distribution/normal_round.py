from typing import List
from fee_simulator.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from fee_simulator.types import RoundLabel
from fee_simulator.core.majority import (
    compute_majority,
    who_is_in_vote_majority,
    normalize_vote,
)
from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT
from fee_simulator.utils import is_appeal_round
from fee_simulator.core.burns import compute_unsuccessful_leader_appeal_burn


def apply_normal_round(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    events = []
    round = transaction_results.rounds[round_index]
    if not round.rotations:
        return events
    votes = round.rotations[-1].votes
    majority = compute_majority(votes)
    if majority == "UNDETERMINED":
        first_addr = next(iter(votes.keys()), None)
        if first_addr:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=first_addr,
                    round_index=round_index,
                    round_label="NORMAL_ROUND",
                    role="LEADER",
                    vote=normalize_vote(votes[first_addr]),
                    hash="0xdefault",  # TODO:Update with actual hash if available
                    cost=0,
                    staked=0,
                    earned=budget.leaderTimeout,
                    slashed=0,
                    burned=0,
                )
            )
            for addr in votes:
                events.append(
                    FeeEvent(
                        sequence_id=event_sequence.next_id(),
                        address=addr,
                        round_index=round_index,
                        round_label="NORMAL_ROUND",
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
    else:
        majority_addresses, minority_addresses = who_is_in_vote_majority(
            votes, majority
        )
        for addr in majority_addresses:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="NORMAL_ROUND",
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
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="NORMAL_ROUND",
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
        first_addr = next(iter(votes), None)
        if first_addr:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=first_addr,
                    round_index=round_index,
                    round_label="NORMAL_ROUND",
                    role="LEADER",
                    vote=normalize_vote(votes[first_addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=budget.leaderTimeout,
                    slashed=0,
                    burned=0,
                )
            )

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
            normal_round_index = round_index - 2  # Default
            for j in range(round_index - 2, -1, -1):
                if not is_appeal_round(round_labels[j]):
                    normal_round_index = j
                    break

            # Compute the appeal bond to know the total amount
            from fee_simulator.core.bond_computing import compute_appeal_bond

            appeal_bond = compute_appeal_bond(
                normal_round_index=normal_round_index,
                leader_timeout=budget.leaderTimeout,
                validators_timeout=budget.validatorsTimeout,
                round_labels=round_labels,
                appeal_round_index=round_index - 1,  # The unsuccessful appeal round
            )

            # Use the burn computation method to calculate how much to burn
            # Since this is a normal round, no fees were paid from the bond
            burn_amount = compute_unsuccessful_leader_appeal_burn(
                appeal_bond, []  # No fees distributed from bond in normal round
            )

            if burn_amount > 0:
                events.append(
                    FeeEvent(
                        sequence_id=event_sequence.next_id(),
                        address=appealant_address,
                        round_index=round_index,
                        round_label="NORMAL_ROUND",
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
