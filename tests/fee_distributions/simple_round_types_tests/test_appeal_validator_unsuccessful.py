import pytest
from fee_simulator.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    Appeal,
    TransactionBudget,
)
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.utils import compute_total_cost, generate_random_eth_address
from fee_simulator.core.bond_computing import compute_appeal_bond
from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT
from fee_simulator.fee_aggregators.address_metrics import (
    compute_total_earnings,
    compute_total_costs,
    compute_total_burnt,
    compute_all_zeros,
)
from fee_simulator.display import (
    display_transaction_results,
    display_fee_distribution,
    display_summary_table,
    display_test_description,
)
from tests.fee_distributions.check_invariants.invariant_checks import check_invariants

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


def test_appeal_validator_unsuccessful(verbose, debug):
    """Test appeal_validator_unsuccessful: normal round (undetermined), appeal unsuccessful."""
    # Setup
    rotation1 = Rotation(
        votes={
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[1]: "AGREE",
            addresses_pool[2]: "AGREE",
            addresses_pool[3]: "DISAGREE",
            addresses_pool[4]: "TIMEOUT",
        }
    )
    rotation2 = Rotation(
        votes={addresses_pool[i]: "AGREE" for i in [5, 6, 7, 8, 9, 10, 11]}
    )
    transaction_results = TransactionRoundResults(
        rounds=[
            Round(rotations=[rotation1]),
            Round(rotations=[rotation2]),
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
            test_name="test_appeal_validator_unsuccessful",
            test_description="This test checks the fee distribution for an unsuccessful validator appeal. It simulates a normal round with an undetermined outcome followed by an appeal round where validators vote in majority agreement. The test verifies that the appealant incurs the appeal bond cost with no earnings, the first leader earns both leader and validator timeouts, the second leader and majority validators earn validator timeouts, minority validators are penalized, and the sender's costs match the transaction cost.",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert
    assert round_labels == [
        "NORMAL_ROUND",
        "APPEAL_VALIDATOR_UNSUCCESSFUL",
    ], f"Expected ['NORMAL_ROUND', 'APPEAL_VALIDATOR_UNSUCCESSFUL'], got {round_labels}"

    # Invariant Check
    check_invariants(fee_events, transaction_budget, transaction_results)

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 23, 1999]
    ), "Everyone else should have no fees"

    # Appealant Fees Assert
    appeal_bond = compute_appeal_bond(
        normal_round_index=0,
        leader_timeout=leaderTimeout,
        validators_timeout=validatorsTimeout,
        round_labels=round_labels,
    )
    assert (
        compute_total_costs(fee_events, addresses_pool[23]) == appeal_bond
    ), f"Appealant should have cost equal to appeal_bond ({appeal_bond})"
    assert (
        compute_total_earnings(fee_events, addresses_pool[23]) == 0
    ), "Appealant should have no earnings"

    # First Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[0])
        == leaderTimeout + validatorsTimeout
    ), f"First leader should earn leaderTimeout ({leaderTimeout}) + validatorsTimeout ({validatorsTimeout})"

    # Second Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[5]) == validatorsTimeout
    ), f"Second leader should earn validatorsTimeout ({validatorsTimeout})"

    # Majority Validator Fees Assert
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i]) == validatorsTimeout
        for i in [6, 7, 8, 9, 10, 11]
    ), f"Majority validators should earn validatorsTimeout ({validatorsTimeout})"

    # Minority Validator Fees Assert
    assert all(
        compute_total_burnt(fee_events, addresses_pool[i])
        == PENALTY_REWARD_COEFFICIENT * validatorsTimeout
        for i in [3, 4]
    ), f"Minority validators should be burned {PENALTY_REWARD_COEFFICIENT * validatorsTimeout}"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, transaction_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"
