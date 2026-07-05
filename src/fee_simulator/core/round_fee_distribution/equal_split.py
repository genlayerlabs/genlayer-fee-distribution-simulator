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

    Fee distribution (contract: bond + round budget divided across ALL
    committee members, leader included, plus the leader fee — measured on
    the driven flows, CON-611):
    - Pool = previous appeal bond + committee_size * validatorsTimeout
    - EVERY committee member (leader included) earns pool // committee_size
      as its validator share (no penalties) — same as the round-0
      undetermined treatment, which also pays the leader's validator share
    - Leader additionally earns leaderTimeout
    - The bond is NOT returned to the sender; the division remainder is
      (1 wei dust on an 11-member split)
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

    # Bond + full round budget split equally across ALL committee members,
    # leader included; the division remainder flows back to the sender.
    committee = list(votes.keys())
    pool = appeal_bond + len(committee) * budget.validatorsTimeout
    share = split_amount(pool, len(committee))

    for addr in committee:
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
                earned=share,
                slashed=0,
                burned=0,
            )
        )

    return events
