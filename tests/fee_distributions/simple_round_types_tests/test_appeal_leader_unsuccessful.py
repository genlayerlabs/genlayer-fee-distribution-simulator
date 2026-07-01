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


def test_appeal_leader_unsuccessful(verbose, debug):
    """Test appeal_leader_unsuccessful: normal round (undetermined), appeal unsuccessful, normal round."""
    # Setup
    rotation1 = Rotation(
        votes={
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[1]: "AGREE",
            addresses_pool[2]: "DISAGREE",
            addresses_pool[3]: "DISAGREE",
            addresses_pool[4]: "TIMEOUT",
        }
    )
    rotation2 = Rotation(
        votes={addresses_pool[i]: "NA" for i in [5, 6, 7, 8, 9, 10, 11]}
    )
    rotation3 = Rotation(
        votes={
            addresses_pool[5]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[2]: "AGREE",
            addresses_pool[3]: "AGREE",
            addresses_pool[4]: "AGREE",
            addresses_pool[1]: "DISAGREE",
            addresses_pool[6]: "DISAGREE",
            addresses_pool[7]: "DISAGREE",
            addresses_pool[8]: "DISAGREE",
            addresses_pool[9]: "DISAGREE",
            addresses_pool[10]: "TIMEOUT",
            addresses_pool[11]: "TIMEOUT",
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
            test_name="test_appeal_leader_unsuccessful",
            test_description="This test validates the fee distribution when a leader appeal is unsuccessful. It sets up a normal round with an undetermined outcome, an appeal round, and a subsequent normal round with no majority. The test ensures the appealant incurs the appeal bond cost without earnings, the first leader and validators earn their timeouts, the second leader and validators share the appeal bond, minority validators are not penalized due to no majority, and the sender's costs are correct.",
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
        "APPEAL_LEADER_UNSUCCESSFUL",
        "EQUAL_SPLIT",
    ], f"Expected ['NORMAL_ROUND', 'APPEAL_LEADER_UNSUCCESSFUL', 'EQUAL_SPLIT'], got {round_labels}"

    # Invariant Check
    check_all_invariants(
        fee_events, transaction_budget, transaction_results, round_labels
    )

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

    # First Leader Fees Assert (Round 1: NORMAL_ROUND undetermined)
    # In undetermined, leader gets leaderTimeout + validatorsTimeout
    assert (
        compute_total_earnings(fee_events, addresses_pool[0])
        == leaderTimeout + validatorsTimeout
    ), f"First leader should earn leaderTimeout ({leaderTimeout}) + validatorsTimeout ({validatorsTimeout})"

    # First Validator Fees Assert (Round 1: NORMAL_ROUND + Round 3: EQUAL_SPLIT)
    # In EQUAL_SPLIT (contract semantics), all non-leader validators earn
    # validatorsTimeout + an equal share of the failed appeal bond
    bond_share = appeal_bond // 10  # 10 non-leader validators in round 3
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i])
        == validatorsTimeout + validatorsTimeout + bond_share  # round1 + round3
        for i in [1, 2, 3, 4]
    ), f"First validators should earn 2*validatorsTimeout + bond share ({2*validatorsTimeout + bond_share})"

    # Second Leader Fees Assert (Round 3: EQUAL_SPLIT)
    # Leader gets leaderTimeout only (excluded from the validator pool,
    # contract skipLeader=true)
    assert (
        compute_total_earnings(fee_events, addresses_pool[5]) == leaderTimeout
    ), f"Second leader should earn leaderTimeout ({leaderTimeout})"

    # Second Validator Fees Assert (Round 3: EQUAL_SPLIT only)
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i])
        == validatorsTimeout + bond_share
        for i in [6, 7, 8, 9, 10, 11]
    ), f"Second validators should earn validatorsTimeout + bond share ({validatorsTimeout + bond_share})"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, transaction_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"
