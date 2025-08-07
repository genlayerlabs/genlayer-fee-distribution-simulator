from typing import List
from fee_simulator.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from fee_simulator.types import RoundLabel


def apply_appeal_leader_unsuccessful(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    """
    Handle unsuccessful leader appeals.
    The appeal bond will be handled in the next round - either distributed
    (SPLIT_PREVIOUS_APPEAL_BOND) or burned (other round types).
    This round itself generates no fee events.
    """
    # No fee events generated in this round
    # The burn will be handled in the subsequent round
    return []
