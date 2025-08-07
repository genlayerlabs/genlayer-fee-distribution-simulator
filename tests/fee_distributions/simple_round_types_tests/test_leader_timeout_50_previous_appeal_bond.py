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
from fee_simulator.fee_aggregators.address_metrics import (
    compute_total_earnings,
    compute_total_costs,
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


def test_leader_timeout_50_previous_appeal_bond(verbose, debug):
    """Test leader_timeout_50_previous_appeal_bond: leader timeout, appeal unsuccessful, leader timeout."""
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
        votes={addresses_pool[i]: "NA" for i in [5, 6, 7, 8, 9, 10, 11]}
    )
    rotation3 = Rotation(
        votes={
            addresses_pool[5]: ["LEADER_TIMEOUT", "NA"],
            addresses_pool[6]: "NA",
            addresses_pool[7]: "NA",
            addresses_pool[8]: "NA",
            addresses_pool[9]: "NA",
            addresses_pool[10]: "NA",
            addresses_pool[11]: "NA",
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
            test_name="test_leader_timeout_50_previous_appeal_bond",
            test_description="This test evaluates the fee distribution for a scenario involving a leader timeout, an unsuccessful appeal, and another leader timeout, labeled as LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND. It sets up three rounds: a leader timeout, an appeal round, and another timeout round. The test confirms that the appealant incurs the appeal bond cost with no earnings, the first leader earns 50% of the leader timeout, the second leader earns half the appeal bond, and the sender's costs match the transaction cost.",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert
    assert round_labels == [
        "LEADER_TIMEOUT_50_PERCENT",
        "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
        "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
    ], f"Expected ['LEADER_TIMEOUT_50_PERCENT', 'APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL', 'LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND'], got {round_labels}"

    # Invariant Check
    check_invariants(fee_events, transaction_budget, transaction_results)

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 5, 23, 1999]
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
        compute_total_earnings(fee_events, addresses_pool[0]) == leaderTimeout * 0.5
    ), f"First leader should earn 50% of leaderTimeout ({leaderTimeout * 0.5})"

    # Second Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[5]) == leaderTimeout * 0.5
    ), f"Second leader should earn 50% of leaderTimeout ({leaderTimeout * 0.5})"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, transaction_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"
