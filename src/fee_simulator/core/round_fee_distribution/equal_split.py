from typing import List
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.core.majority import normalize_vote


def apply_equal_split(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    """
    Distribute fees for an EQUAL_SPLIT round (Solidity Type 4).

    This occurs when:
    - Previous round was APPEAL_LEADER_UNSUCCESSFUL
    - Current round has UNDETERMINED majority

    Fee distribution:
    - Leader: earns leaderTimeout
    - ALL validators: earn validatorsTimeout equally (no penalties)
    - The appeal bond from the previous unsuccessful appeal is returned to sender
      (handled via refunds, not distributed to validators)
    """
    events = []
    round_obj = transaction_results.rounds[round_index]
    if not round_obj.rotations:
        return events

    votes = round_obj.rotations[-1].votes

    # Leader gets leaderTimeout
    first_addr = next(iter(votes.keys()), None)
    if first_addr:
        events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=first_addr,
                round_index=round_index,
                round_label="EQUAL_SPLIT",
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

    # ALL validators get validatorsTimeout equally (no penalties)
    for addr in votes:
        events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=addr,
                round_index=round_index,
                round_label="EQUAL_SPLIT",
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

    return events
