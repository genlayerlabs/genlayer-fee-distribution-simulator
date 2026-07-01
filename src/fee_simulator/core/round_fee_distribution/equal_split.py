from typing import List
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.core.majority import normalize_vote
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.utils import split_amount


def apply_equal_split(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    """
    Distribute fees for an EQUAL_SPLIT round, mirroring the contract's
    handler (FeesProcessor.processFeesForTx, EQUAL_SPLIT branch):

    This occurs when:
    - Previous round was APPEAL_LEADER_UNSUCCESSFUL
    - Current round has UNDETERMINED majority

    Fee distribution (contract: _distributeFeesToValidators with
    skipLeader=true, distributeToAll=true, extra=previousAppealBond):
    - Leader: earns leaderTimeout only (excluded from the validator pool)
    - ALL non-leader validators: earn validatorsTimeout + an equal share of
      the previous appeal bond (no penalties)
    - The bond is NOT returned to the sender; the division remainder is
    """
    events = []
    round_obj = transaction_results.rounds[round_index]
    if not round_obj.rotations:
        return events

    votes = round_obj.rotations[-1].votes

    # Leader gets leaderTimeout (and nothing from the validator pool)
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

    # Previous unsuccessful leader appeal bond, distributed to the pool
    appeal_bond = 0
    if round_index >= 1 and budget.appeals:
        appeal_bond = compute_appeal_bond(
            normal_round_index=round_index - 2 if round_index >= 2 else 0,
            leader_timeout=budget.leaderTimeout,
            validators_timeout=budget.validatorsTimeout,
            round_labels=round_labels,
            rotations=budget.rotations,
            appeal_round_index=round_index - 1,
        )

    validator_addresses = [addr for addr in votes if addr != first_addr]
    bond_share = split_amount(appeal_bond, len(validator_addresses))

    # ALL non-leader validators get validatorsTimeout + bond share (no penalties)
    for addr in validator_addresses:
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
                earned=budget.validatorsTimeout + bond_share,
                slashed=0,
                burned=0,
            )
        )

    return events
