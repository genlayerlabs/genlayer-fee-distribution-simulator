from typing import List
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from src.fee_simulator.protocol.types import RoundLabel


def apply_appeal_leader_timeout_unsuccessful(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    """
    Handle unsuccessful leader timeout appeals.
    The appeal bond will be handled in the next round (LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND)
    where most of it will be burned after the leader gets their 50 wei.
    This round itself generates no fee events.
    """
    # No fee events generated in this round
    # The burn will be handled in the subsequent round
    return []
