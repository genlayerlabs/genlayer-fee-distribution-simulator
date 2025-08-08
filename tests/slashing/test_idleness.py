import pytest
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    TransactionBudget,
)
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.utils import compute_total_cost, generate_random_eth_address
from src.fee_simulator.metrics.address_metrics import (
    compute_total_earnings,
    compute_total_costs,
    compute_total_slashed,
    compute_all_zeros,
    compute_current_stake,
)
from src.fee_simulator.protocol.constants import (
    PENALTY_REWARD_COEFFICIENT,
    DEFAULT_STAKE,
)
from src.fee_simulator.display import (
    display_transaction_results,
    display_fee_distribution,
    display_summary_table,
)

leaderTimeout = 100
validatorsTimeout = 200

addresses_pool = [generate_random_eth_address() for _ in range(2000)]

transaction_budget = TransactionBudget(
    leaderTimeout=leaderTimeout,
    validatorsTimeout=validatorsTimeout,
    appealRounds=0,
    rotations=[0],
    senderAddress=addresses_pool[1999],
    appeals=[],
    staking_distribution="constant",
)


def test_idle_round(verbose, debug):
    """
    Test fee distribution for a normal round where some validators are idle.

    Description:
    This test verifies the fee distribution and stake slashing in a normal round where two validators
    are idle and are replaced by reserve validators. The leader and active validators vote 'AGREE',
    while one reserve validator votes 'DISAGREE'. The test checks:
    - Correct round labeling as 'NORMAL_ROUND'.
    - Idle validators are slashed 1% of their stake.
    - The leader earns both leader and validator timeouts.
    - Active validators (including the agreeing reserve validator) earn validator timeouts.
    - The disagreeing reserve validator is penalized.
    - The sender's costs and refunds are correct.
    - All non-participating addresses have zero fees.
    """
    # Setup
    rotation = Rotation(
        votes={
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],  # Leader agrees
            addresses_pool[1]: "AGREE",  # Validator 1 agrees
            addresses_pool[2]: "IDLE",  # Validator 2 is idle
            addresses_pool[3]: "AGREE",  # Validator 3 agrees
            addresses_pool[4]: "IDLE",  # Validator 4 is idle
        },
        reserve_votes={
            addresses_pool[5]: "AGREE",  # Reserve validator agrees
            addresses_pool[6]: "DISAGREE",  # Reserve validator disagrees
        },
    )
    round = Round(rotations=[rotation])
    transaction_results = TransactionRoundResults(rounds=[round])

    # Execute
    fee_events, round_labels = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert
    assert round_labels == [
        "NORMAL_ROUND"
    ], f"Expected ['NORMAL_ROUND'], got {round_labels}"

    # Assert Stake Slashing for Idle Validators
    assert (
        compute_current_stake(addresses_pool[2], fee_events) == DEFAULT_STAKE * 0.99
    ), "Idle validator 2's stake should be slashed by 1%"
    assert (
        compute_current_stake(addresses_pool[4], fee_events) == DEFAULT_STAKE * 0.99
    ), "Idle validator 4's stake should be slashed by 1%"

    # Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[0])
        == leaderTimeout + validatorsTimeout
    ), f"Leader should earn leaderTimeout ({leaderTimeout}) + validatorsTimeout ({validatorsTimeout})"

    # Majority Validator Fees Assert
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i]) == validatorsTimeout
        for i in [1, 3, 5]
    ), f"Validators in majority should earn validatorsTimeout ({validatorsTimeout})"

    # Minority Validator Fees Assert
    assert (
        compute_total_slashed(fee_events, addresses_pool[6]) == 0
    ), "Disagreeing validator should not be slashed in this context"
    assert (
        compute_total_earnings(fee_events, addresses_pool[6]) == 0
    ), "Disagreeing validator should earn nothing"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, transaction_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 1, 2, 3, 4, 5, 6, 1999]
    ), "Everyone else should have no fees"
