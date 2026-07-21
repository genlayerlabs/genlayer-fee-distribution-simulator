import pytest
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    Appeal,
    TransactionBudget,
)
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.utils import compute_total_cost, generate_random_eth_address
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.protocol.constants import PENALTY_REWARD_COEFFICIENT
from src.fee_simulator.metrics.address_metrics import (
    compute_total_earnings,
    compute_total_costs,
    compute_total_burnt,
    compute_all_zeros,
)
from src.fee_simulator.display import (
    display_transaction_results,
    display_fee_distribution,
    display_summary_table,
    display_test_description,
)
from src.fee_simulator.specification.invariants.checker import check_all_invariants

leaderTimeout = 100
validatorsTimeout = 200

addresses_pool = [generate_random_eth_address() for _ in range(2000)]

transaction_budget = TransactionBudget(
    leaderTimeout=leaderTimeout,
    validatorsTimeout=validatorsTimeout,
    appealRounds=1,
    rotations=[0, 0],
    senderAddress=addresses_pool[1999],
    appeals=[Appeal(appealantAddress=addresses_pool[23])],
    staking_distribution="constant",
)


def test_leader_timeout_150_previous_normal_round(verbose, debug):
    """Test leader_timeout_150_previous_normal_round: leader timeout, appeal successful, normal round.

    Spec semantics (RoundsCreation.createNewLeaderTimeoutAppealRound): the
    leader-timeout appeal keeps the SAME validator set, drops the timed-out
    leader, and elects the validator at index L % (N-1) of the reduced array
    as the new leader — no new validators are added. The appeal round itself
    has no voting committee; it keeps NA bookkeeping over the appealed
    round's committee. The induced re-execution round therefore has N-1
    members (here: leader + 2 agree + 1 disagree on the 4-member remaining
    committee).
    """
    # Setup
    rotation1 = Rotation(
        votes={
            addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
            addresses_pool[1]: "NA",
            addresses_pool[2]: "NA",
            addresses_pool[3]: "NA",
            addresses_pool[4]: "NA",
        }
    )
    rotation2 = Rotation(
        votes={addresses_pool[i]: "NA" for i in [0, 1, 2, 3, 4]}
    )
    rotation3 = Rotation(
        votes={
            addresses_pool[1]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[2]: "AGREE",
            addresses_pool[3]: "AGREE",
            addresses_pool[4]: "DISAGREE",
        }
    )
    transaction_results = TransactionRoundResults(
        rounds=[
            Round(rotations=[rotation1]),
            Round(rotations=[rotation2]),
            Round(rotations=[rotation3]),
        ]
    )

    # Execute
    fee_events, round_labels = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_leader_timeout_150_previous_normal_round",
            test_description="This test assesses the fee distribution for a leader timeout scenario followed by a successful appeal and a normal round, labeled as LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND. It involves a leader timeout round, an appeal round, and a normal round with a majority agreement. The test ensures the appealant earns the appeal bond plus half the leader timeout, the second leader earns 150% of the leader timeout plus validator timeout, majority validators earn validator timeouts, minority validators are penalized, and the sender's costs are correct.",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert
    assert round_labels == [
        "SKIP_ROUND",
        "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
        "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
    ], f"Expected ['SKIP_ROUND', 'APPEAL_LEADER_TIMEOUT_SUCCESSFUL', 'LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND'], got {round_labels}"

    # Invariant Check
    check_all_invariants(
        fee_events, transaction_budget, transaction_results, round_labels, tolerance=20
    )

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 1, 2, 3, 4, 23, 1999]
    ), "Everyone else should have no fees"

    # Appealant Fees Assert (bond still quoted from the round-size table at
    # the appealed round's index — 1 x (100 + 5 x 200) = 1100 — even though
    # the induced round seats one fewer body)
    appeal_bond = compute_appeal_bond(
        normal_round_index=0,
        leader_timeout=leaderTimeout,
        validators_timeout=validatorsTimeout,
        round_labels=round_labels,
    )
    assert appeal_bond == leaderTimeout + 5 * validatorsTimeout
    assert compute_total_earnings(fee_events, addresses_pool[23]) == int(
        appeal_bond * 1.5
    ), f"Appealant should earn 1.5x appeal_bond ({int(appeal_bond * 1.5)}) for 50% return"
    assert (
        compute_total_costs(fee_events, addresses_pool[23]) == appeal_bond
    ), f"Appealant should have cost equal to appeal_bond ({appeal_bond})"

    # First Leader Fees Assert (timed-out leader is dropped from the induced
    # round and earns nothing)
    assert (
        compute_total_earnings(fee_events, addresses_pool[0]) == 0
    ), f"First leader should earn 0"

    # Second Leader Fees Assert (the validator that followed the timed-out
    # leader in the original order: 150 leader fee + 200 validator share)
    assert (
        compute_total_earnings(fee_events, addresses_pool[1])
        == leaderTimeout * 1.5 + validatorsTimeout
    ), f"Second leader should earn 150% of leaderTimeout plus validator share ({leaderTimeout * 1.5 + validatorsTimeout})"

    # Majority Validator Fees Assert
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i]) == validatorsTimeout
        for i in [2, 3]
    ), f"Majority validators should earn validatorsTimeout ({validatorsTimeout})"

    # Minority Validator Fees Assert
    assert all(
        compute_total_burnt(fee_events, addresses_pool[i])
        == PENALTY_REWARD_COEFFICIENT * validatorsTimeout
        for i in [4]
    ), f"Minority validators should be burned {PENALTY_REWARD_COEFFICIENT * validatorsTimeout}"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, transaction_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"
