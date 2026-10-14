"""Exact F1a sequence: a later winning leader appeal invalidates a failed bond's payout round."""

from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.protocol.models import (
    Appeal,
    Rotation,
    Round,
    TransactionBudget,
    TransactionRoundResults,
)
from src.fee_simulator.utils import generate_random_eth_address


def test_failed_leader_bond_preceding_skip_is_burned_not_refunded():
    addresses = [generate_random_eth_address() for _ in range(100)]
    appealer = addresses[80]

    def normal_round(size: int, accepted: bool) -> Round:
        votes = {addresses[0]: ["LEADER_RECEIPT", "AGREE"]}
        for index in range(1, size):
            votes[addresses[index]] = (
                "AGREE"
                if accepted or index % 3 == 0
                else ("DISAGREE" if index % 3 == 1 else "TIMEOUT")
            )
        return Round(rotations=[Rotation(votes=votes)])

    def leader_appeal(first: int, size: int) -> Round:
        return Round(
            rotations=[
                Rotation(votes={addresses[index]: "NA" for index in range(first, first + size)})
            ]
        )

    rounds = TransactionRoundResults(
        rounds=[
            normal_round(5, False),
            leader_appeal(5, 7),
            normal_round(11, False),
            leader_appeal(12, 13),
            normal_round(23, True),
        ]
    )
    budget = TransactionBudget(
        leaderTimeout=100,
        validatorsTimeout=200,
        appealRounds=2,
        rotations=[0, 0, 0],
        senderAddress=addresses[99],
        appeals=[Appeal(appealantAddress=appealer), Appeal(appealantAddress=appealer)],
        staking_distribution="constant",
    )

    events, labels = process_transaction(
        addresses=addresses,
        transaction_results=rounds,
        transaction_budget=budget,
    )
    assert labels == [
        "NORMAL_ROUND",
        "APPEAL_LEADER_UNSUCCESSFUL",
        "SKIP_ROUND",
        "APPEAL_LEADER_SUCCESSFUL",
        "NORMAL_ROUND",
    ]
    failed = [event for event in events if event.round_index == 1 and event.role == "APPEALANT"]
    assert sum(event.cost for event in failed) == 2300
    skipped = [event for event in events if event.round_index == 2]
    assert sum(event.burned for event in skipped) == 2300
    assert sum(event.earned for event in skipped) == 0

    winner = [
        event
        for event in events
        if event.round_index == 3 and event.role == "APPEALANT" and event.address == appealer
    ]
    assert sum(event.cost for event in winner) == 4700
    assert sum(event.earned for event in winner) == 11750  # Principal 4700 + profit 7050.
