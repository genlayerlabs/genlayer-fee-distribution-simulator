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
    appealRounds=0,
    rotations=[0],
    senderAddress=addresses_pool[1999],
    appeals=[],
    staking_distribution="constant",
)


def test_leader_timeout_50_percent(verbose, debug):
    """Test fee distribution for a leader timeout round."""
    # Setup
    rotation = Rotation(
        votes={
            addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
            addresses_pool[1]: "NA",
            addresses_pool[2]: "NA",
            addresses_pool[3]: "NA",
            addresses_pool[4]: "NA",
        }
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
        display_test_description(
            test_name="test_leader_timeout_50_percent",
            test_description="This test verifies the fee distribution for a single leader timeout round, labeled as LEADER_TIMEOUT_50_PERCENT. It simulates a round where the leader times out, and no validators vote. The test checks that the leader earns 50% of the leader timeout, all other participants (except the sender) have zero fees, and the sender's costs equal the total transaction cost.",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert
    assert round_labels == [
        "LEADER_TIMEOUT_50_PERCENT"
    ], f"Expected ['LEADER_TIMEOUT_50_PERCENT'], got {round_labels}"

    # Invariant Check
    check_all_invariants(
        fee_events, transaction_budget, transaction_results, round_labels
    )

    # Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[0]) == leaderTimeout * 0.5
    ), f"Leader should earn 50% of leaderTimeout ({leaderTimeout * 0.5})"

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 1999]
    ), "Everyone else should have no fees"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, transaction_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"
