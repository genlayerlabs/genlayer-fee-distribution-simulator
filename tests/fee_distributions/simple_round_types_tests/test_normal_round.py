from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.utils import compute_total_cost, generate_random_eth_address
from fee_simulator.display import (
    display_transaction_results,
    display_fee_distribution,
    display_summary_table,
    display_test_description,
)
from fee_simulator.fee_aggregators.address_metrics import (
    compute_all_zeros,
    compute_total_costs,
    compute_total_earnings,
    compute_total_burnt,
    compute_total_balance,
)
from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT
from tests.fee_distributions.check_invariants.comprehensive_invariants import (
    check_comprehensive_invariants,
)

leaderTimeout = 100
validatorsTimeout = 200

addresses_pool = [generate_random_eth_address() for _ in range(2000)]
sender_address = addresses_pool[1999]
appealant_address = addresses_pool[1998]


def test_normal_round(verbose, debug):
    """Test fee distribution for a normal round with all validators agreeing."""
    # Create custom transaction with unanimous agreement
    from fee_simulator.models import (
        TransactionRoundResults,
        TransactionBudget,
        Round,
        Rotation,
        Appeal,
    )

    # Create votes where all validators agree
    votes = {
        addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],  # Leader
        addresses_pool[1]: "AGREE",
        addresses_pool[2]: "AGREE",
        addresses_pool[3]: "AGREE",
        addresses_pool[4]: "AGREE",
    }

    transaction_results = TransactionRoundResults(
        rounds=[Round(rotations=[Rotation(votes=votes)])]
    )

    transaction_budget = TransactionBudget(
        leaderTimeout=leaderTimeout,
        validatorsTimeout=validatorsTimeout,
        appealRounds=0,
        rotations=[0],
        senderAddress=sender_address,
        appeals=[],
        staking_distribution="constant",
    )

    # Get round labels
    round_labels = label_rounds(transaction_results)

    # Process transaction
    fee_events, _ = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_normal_round",
            test_description="This test verifies the fee distribution for a normal round with all validators agreeing. It sets up a round with a majority agreement, and verifies that the leader earns the leader timeout plus validator timeout, validators earn the validator timeout, and the sender's costs match the total transaction cost.",
        )
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

    # Invariant Check
    check_comprehensive_invariants(
        fee_events, transaction_budget, transaction_results, round_labels
    )

    # Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[0])
        == leaderTimeout + validatorsTimeout
    ), "Leader should have 100 (leader) + 200 (validator)"

    # Validator Fees Assert
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i]) == validatorsTimeout
        for i in [1, 2, 3, 4]
    ), "Validator should have 200"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, sender_address) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 1, 2, 3, 4, 1999]
    ), "Everyone else should have no fees in normal round"


def test_normal_round_with_minority_penalties(verbose, debug):
    """Test normal round with penalties for validators in the minority (majority agrees)."""
    # Define path - majority agrees (which means some disagree/timeout)
    # Note: The path_to_transaction_results will create a scenario with majority agree
    # but some validators in minority. This is handled by the vote distribution logic.
    path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]

    # The path_to_transaction_results will create a scenario with majority agree
    # but some validators in minority who will be penalized

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

    # Process transaction
    fee_events, _ = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_normal_round_with_minority_penalties",
            test_description="This test verifies the fee distribution for a normal round with penalties for validators in the minority.",
        )
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

    # Invariant Check
    check_comprehensive_invariants(
        fee_events, transaction_budget, transaction_results, round_labels
    )

    # Check that there are both earnings and burns (indicating majority/minority split)
    total_earnings = sum(
        e.earned for e in fee_events if e.earned and e.role == "VALIDATOR"
    )
    total_burns = sum(
        e.burned for e in fee_events if e.burned and e.role == "VALIDATOR"
    )
    assert total_earnings > 0, "Should have validator earnings"
    assert total_burns > 0, "Should have validator burns for minority"


def test_normal_round_no_majority(verbose, debug):
    """Test normal round with no majority (undetermined)."""
    # Define path - undetermined (no clear majority)
    path = ["START", "LEADER_RECEIPT_UNDETERMINED", "END"]

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

    # Process transaction
    fee_events, _ = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_normal_round_no_majority",
            test_description="This test verifies the fee distribution for a normal round with no majority (undetermined).",
        )
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

    # Invariant Check
    check_comprehensive_invariants(
        fee_events, transaction_budget, transaction_results, round_labels
    )

    # Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[0])
        == leaderTimeout + validatorsTimeout
    ), "Leader should have 100 (leader) + 200 (validator) in undetermined round"

    # Validator Fees Assert - all validators should earn in undetermined
    validator_earnings = [
        compute_total_earnings(fee_events, addr) for addr in addresses_pool[1:5]
    ]
    assert all(
        earning == validatorsTimeout for earning in validator_earnings
    ), "All validators should have 200 due to no majority"

    # No burns in undetermined round
    total_burns = sum(e.burned for e in fee_events if e.burned)
    assert total_burns == 0, "Should have no burns in undetermined round"


def test_normal_round_majority_disagree(verbose, debug):
    """Test normal round with majority DISAGREE."""
    # Define path - majority disagrees
    path = ["START", "LEADER_RECEIPT_MAJORITY_DISAGREE", "END"]

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

    # Process transaction
    fee_events, _ = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_normal_round_majority_disagree",
            test_description="This test verifies the fee distribution for a normal round with majority DISAGREE.",
        )
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

    # Invariant Check
    check_comprehensive_invariants(
        fee_events, transaction_budget, transaction_results, round_labels
    )

    # Leader Fees Assert
    # In our implementation, the leader also disagrees (part of majority)
    assert (
        compute_total_earnings(fee_events, addresses_pool[0])
        == leaderTimeout + validatorsTimeout
    ), "Leader should have 100 (leader) + 200 (validator) as part of majority"

    # Check that minority validators burn
    # Find validators who are in minority (those who agreed or timed out)
    total_burns = sum(
        e.burned for e in fee_events if e.burned and e.role == "VALIDATOR"
    )
    assert total_burns > 0, "Should have burns from minority validators"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, sender_address) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"
