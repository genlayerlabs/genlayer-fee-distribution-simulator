import pytest
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.core.path_to_transaction import path_to_transaction_results
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
from tests.fee_distributions.check_invariants.comprehensive_invariants import (
    check_comprehensive_invariants,
)

leaderTimeout = 100
validatorsTimeout = 200

addresses_pool = [generate_random_eth_address() for _ in range(2000)]
sender_address = addresses_pool[1999]
appealant_address = addresses_pool[23]


def test_appeal_validator_successful(verbose, debug):
    """Test appeal_validator_successful: normal round (majority agree), appeal successful, normal round."""
    # Define path - validator appeal after majority agree
    path = [
        "START",
        "LEADER_RECEIPT_MAJORITY_AGREE",  # Normal round where majority agreed
        "VALIDATOR_APPEAL_SUCCESSFUL",  # Validators appeal and succeed
        "LEADER_RECEIPT_MAJORITY_AGREE",  # Normal round after successful appeal
        "END",
    ]

    # Convert path to transaction results
    transaction_results, transaction_budget = path_to_transaction_results(
        path=path,
        addresses=addresses_pool,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=leaderTimeout,
        validators_timeout=validatorsTimeout,
    )

    # Get round labels
    round_labels = label_rounds(transaction_results)

    # Execute
    fee_events, _ = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_appeal_validator_successful",
            test_description="This test evaluates the fee distribution for a successful validator appeal. It involves a normal round with a majority agreement, an appeal round where validators successfully appeal, and a normal round after the appeal. The test confirms that the appealant earns the appeal bond plus the leader timeout, and that the special case patterns are applied correctly.",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert - should have special pattern applied
    assert round_labels == [
        "SKIP_ROUND",  # Special case: normal round before successful appeal becomes SKIP_ROUND
        "APPEAL_VALIDATOR_SUCCESSFUL",
        "NORMAL_ROUND",
    ], f"Expected ['SKIP_ROUND', 'APPEAL_VALIDATOR_SUCCESSFUL', 'NORMAL_ROUND'], got {round_labels}"

    # Invariant Check
    check_comprehensive_invariants(
        fee_events, transaction_budget, transaction_results, round_labels
    )

    # Appealant Fees Assert
    appeal_bond = compute_appeal_bond(
        normal_round_index=0,
        leader_timeout=leaderTimeout,
        validators_timeout=validatorsTimeout,
        round_labels=round_labels,
    )
    appealant_earnings = compute_total_earnings(fee_events, appealant_address)
    assert appealant_earnings == int(
        appeal_bond * 1.5
    ), f"Appealant should earn 1.5x appeal_bond ({int(appeal_bond * 1.5)}) for 50% return, got {appealant_earnings}"

    appealant_costs = compute_total_costs(fee_events, appealant_address)
    assert (
        appealant_costs == appeal_bond
    ), f"Appealant should have cost equal to appeal_bond ({appeal_bond}), got {appealant_costs}"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    sender_costs = compute_total_costs(fee_events, sender_address)
    assert (
        sender_costs == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}, got {sender_costs}"

    # Check that fee distribution follows expected patterns
    # In a successful validator appeal, the appealant gets the leader timeout
    # and the appeal bond is returned
    total_earnings = sum(e.earned for e in fee_events if e.earned)
    total_burns = sum(e.burned for e in fee_events if e.burned)
    assert total_earnings > 0, "Should have positive earnings"


def test_appeal_validator_successful_after_disagree(verbose, debug):
    """Test leader appeal after a majority disagree round."""
    # Define path - leader appeal after majority disagree (only valid option)
    path = [
        "START",
        "LEADER_RECEIPT_MAJORITY_DISAGREE",  # Normal round where majority disagreed
        "LEADER_APPEAL_SUCCESSFUL",  # Leader appeals and succeeds
        "LEADER_RECEIPT_MAJORITY_AGREE",  # Normal round after successful appeal
        "END",
    ]

    # Convert path to transaction results
    transaction_results, transaction_budget = path_to_transaction_results(
        path=path,
        addresses=addresses_pool,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=leaderTimeout,
        validators_timeout=validatorsTimeout,
    )

    # Get round labels
    round_labels = label_rounds(transaction_results)

    # Execute
    fee_events, _ = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_appeal_validator_successful_after_disagree",
            test_description="This test evaluates the fee distribution for a successful leader appeal after a majority disagree round.",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert - should have special pattern applied
    assert round_labels == [
        "SKIP_ROUND",  # Special case: normal round before successful appeal becomes SKIP_ROUND
        "APPEAL_LEADER_SUCCESSFUL",  # Leader appeal after disagree
        "NORMAL_ROUND",
    ], f"Expected ['SKIP_ROUND', 'APPEAL_LEADER_SUCCESSFUL', 'NORMAL_ROUND'], got {round_labels}"

    # Invariant Check
    check_comprehensive_invariants(
        fee_events, transaction_budget, transaction_results, round_labels
    )

    # Appealant should earn appeal bond + leader timeout
    appeal_bond = compute_appeal_bond(
        normal_round_index=0,
        leader_timeout=leaderTimeout,
        validators_timeout=validatorsTimeout,
        round_labels=round_labels,
    )
    appealant_earnings = compute_total_earnings(fee_events, appealant_address)
    assert appealant_earnings == int(
        appeal_bond * 1.5
    ), f"Appealant should earn 1.5x appeal_bond ({int(appeal_bond * 1.5)}) for 50% return, got {appealant_earnings}"
