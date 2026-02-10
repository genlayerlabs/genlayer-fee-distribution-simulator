"""
Test cases specifically for chained unsuccessful appeals.

This is a critical edge case for financial systems where multiple
unsuccessful appeals can occur in sequence.
"""

import pytest
from typing import List
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    TransactionBudget,
    Appeal,
)
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.utils import generate_random_eth_address
from src.fee_simulator.metrics.address_metrics import (
    compute_total_costs,
    compute_total_earnings,
    compute_total_burnt,
)
from src.fee_simulator.display import (
    display_transaction_results,
    display_fee_distribution,
    display_summary_table,
)

# Generate address pool
addresses_pool = [generate_random_eth_address() for _ in range(2000)]


class TestChainedUnsuccessfulAppeals:
    """Test cases for chains of unsuccessful appeals."""

    def test_double_validator_unsuccessful_appeal(self, verbose=False):
        """Test two consecutive unsuccessful validator appeals."""
        # Setup: Normal (majority) → Appeal (unsuccessful) → Appeal (unsuccessful) → Normal
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal round with majority AGREE
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 1: First appeal (validators still agree - unsuccessful)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[4]: "AGREE",
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "DISAGREE",
                                addresses_pool[8]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 2: Normal round (could trigger another appeal)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[9]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[10]: "AGREE",
                                addresses_pool[11]: "AGREE",
                                addresses_pool[12]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 3: Second appeal (validators still agree - unsuccessful)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[13]: "AGREE",
                                addresses_pool[14]: "AGREE",
                                addresses_pool[15]: "AGREE",
                                addresses_pool[16]: "DISAGREE",
                                addresses_pool[17]: "DISAGREE",
                                addresses_pool[18]: "TIMEOUT",
                            }
                        )
                    ]
                ),
                # Round 4: Final normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[19]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[20]: "AGREE",
                                addresses_pool[21]: "DISAGREE",
                                addresses_pool[22]: "DISAGREE",
                                addresses_pool[23]: "TIMEOUT",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)

        if verbose:
            display_transaction_results(transaction_results, labels)
            print(f"Labels: {labels}")

        # Verify labeling
        assert labels[0] == "NORMAL_ROUND"
        assert labels[1] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert (
            labels[2] == "NORMAL_ROUND"
        )  # Not SPLIT_PREVIOUS_APPEAL_BOND because not undetermined
        assert labels[3] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert (
            labels[4] == "SPLIT_PREVIOUS_APPEAL_BOND"
        )  # This is undetermined after unsuccessful appeal

    def test_triple_chained_unsuccessful_appeals(self):
        """Test three consecutive unsuccessful appeals."""
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal round with majority
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 1: First unsuccessful appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[4]: "AGREE",
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 2: Normal round with majority (triggers another appeal)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[8]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "AGREE",
                                addresses_pool[11]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 3: Second unsuccessful appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[12]: "AGREE",
                                addresses_pool[13]: "AGREE",
                                addresses_pool[14]: "AGREE",
                                addresses_pool[15]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 4: Normal round with majority (triggers third appeal)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[16]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[17]: "AGREE",
                                addresses_pool[18]: "AGREE",
                                addresses_pool[19]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 5: Third unsuccessful appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[20]: "AGREE",
                                addresses_pool[21]: "AGREE",
                                addresses_pool[22]: "AGREE",
                                addresses_pool[23]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 6: Final normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[24]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[25]: "AGREE",
                                addresses_pool[26]: "AGREE",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)

        # All appeals should be unsuccessful
        assert labels[1] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert labels[3] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert labels[5] == "APPEAL_VALIDATOR_UNSUCCESSFUL"

        # Normal rounds between appeals
        assert labels[0] == "NORMAL_ROUND"
        assert labels[2] == "NORMAL_ROUND"
        assert labels[4] == "NORMAL_ROUND"
        assert labels[6] == "NORMAL_ROUND"

    def test_mixed_leader_validator_unsuccessful_chain(self):
        """Test chain of mixed leader and validator unsuccessful appeals."""
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal round undetermined (triggers leader appeal)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "DISAGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "TIMEOUT",
                            }
                        )
                    ]
                ),
                # Round 1: Leader appeal (unsuccessful - next round still undetermined)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[5]: "NA",
                                addresses_pool[6]: "NA",
                                addresses_pool[7]: "NA",
                            }
                        )
                    ]
                ),
                # Round 2: Normal round still undetermined (appeal was unsuccessful)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[8]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "DISAGREE",
                                addresses_pool[11]: "DISAGREE",
                                addresses_pool[12]: "TIMEOUT",
                            }
                        )
                    ]
                ),
                # Round 3: Another leader appeal (successful - next round has majority)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[13]: "NA",
                                addresses_pool[14]: "NA",
                                addresses_pool[15]: "NA",
                                addresses_pool[16]: "NA",
                            }
                        )
                    ]
                ),
                # Round 4: Final round with clear majority
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[17]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[18]: "AGREE",
                                addresses_pool[19]: "AGREE",
                                addresses_pool[20]: "DISAGREE",
                                addresses_pool[21]: "TIMEOUT",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)

        assert labels[0] == "NORMAL_ROUND"
        assert labels[1] == "APPEAL_LEADER_UNSUCCESSFUL"
        assert labels[2] == "SKIP_ROUND"  # Skip round due to successful appeal after
        assert (
            labels[3] == "APPEAL_LEADER_SUCCESSFUL"
        )  # Successful because next round has majority
        assert labels[4] == "NORMAL_ROUND"  # Normal round with majority

    def test_leader_timeout_unsuccessful_chain(self):
        """Test chain involving leader timeout unsuccessful appeals."""
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Leader timeout
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[1]: "NA",
                                addresses_pool[2]: "NA",
                            }
                        )
                    ]
                ),
                # Round 1: Appeal (unsuccessful - another timeout)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[3]: "NA",
                                addresses_pool[4]: "NA",
                                addresses_pool[5]: "NA",
                            }
                        )
                    ]
                ),
                # Round 2: Another leader timeout
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[6]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[7]: "NA",
                                addresses_pool[8]: "NA",
                            }
                        )
                    ]
                ),
                # Round 3: Another appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[9]: "NA",
                                addresses_pool[10]: "NA",
                                addresses_pool[11]: "NA",
                            }
                        )
                    ]
                ),
                # Round 4: Final leader timeout
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[12]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[13]: "NA",
                                addresses_pool[14]: "NA",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)

        assert labels[0] == "LEADER_TIMEOUT_50_PERCENT"  # First leader timeout gets 50%
        assert labels[1] == "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL"
        assert labels[2] == "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND"
        assert labels[3] == "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL"
        assert labels[4] == "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND"

    def test_fee_distribution_with_chained_appeals(self, verbose=False):
        """Test that fee distribution works correctly with chained unsuccessful appeals."""
        # Setup transaction budget with multiple appeals
        transaction_budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=3,
            rotations=[0, 0, 0, 0],
            senderAddress=addresses_pool[1999],
            appeals=[
                Appeal(appealantAddress=addresses_pool[1998]),
                Appeal(appealantAddress=addresses_pool[1997]),
                Appeal(appealantAddress=addresses_pool[1996]),
            ],
            staking_distribution="constant",
        )

        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 1: First appeal (unsuccessful)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[4]: "AGREE",
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 2: Normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[8]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "AGREE",
                                addresses_pool[11]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 3: Second appeal (unsuccessful)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[12]: "AGREE",
                                addresses_pool[13]: "AGREE",
                                addresses_pool[14]: "AGREE",
                                addresses_pool[15]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 4: Normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[16]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[17]: "AGREE",
                                addresses_pool[18]: "AGREE",
                                addresses_pool[19]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 5: Third appeal (unsuccessful)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[20]: "AGREE",
                                addresses_pool[21]: "AGREE",
                                addresses_pool[22]: "AGREE",
                                addresses_pool[23]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 6: Final normal round (undetermined to trigger split)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[24]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[25]: "AGREE",
                                addresses_pool[26]: "DISAGREE",
                                addresses_pool[27]: "DISAGREE",
                                addresses_pool[28]: "TIMEOUT",
                            }
                        )
                    ]
                ),
            ]
        )

        # Process transaction
        fee_events, round_labels = process_transaction(
            addresses_pool, transaction_results, transaction_budget
        )

        if verbose:
            display_summary_table(
                fee_events, transaction_results, transaction_budget, round_labels
            )
            display_fee_distribution(fee_events)

        # Verify all appeals are labeled as unsuccessful
        assert round_labels[1] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert round_labels[3] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert round_labels[5] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert round_labels[6] == "SPLIT_PREVIOUS_APPEAL_BOND"

        # Verify appeal bonds are charged correctly
        appeal_bond_1 = compute_appeal_bond(0, 100, 200, round_labels)
        appeal_bond_2 = compute_appeal_bond(2, 100, 200, round_labels)
        appeal_bond_3 = compute_appeal_bond(4, 100, 200, round_labels)

        # Each appealant should have paid their bond but earned nothing
        assert compute_total_costs(fee_events, addresses_pool[1998]) == appeal_bond_1
        assert compute_total_earnings(fee_events, addresses_pool[1998]) == 0

        assert compute_total_costs(fee_events, addresses_pool[1997]) == appeal_bond_2
        assert compute_total_earnings(fee_events, addresses_pool[1997]) == 0

        assert compute_total_costs(fee_events, addresses_pool[1996]) == appeal_bond_3
        assert compute_total_earnings(fee_events, addresses_pool[1996]) == 0

        # The bond from the last unsuccessful appeal should be split in round 6
        # among validators since it's undetermined
        round_6_validators = [addresses_pool[i] for i in range(24, 29)]
        for addr in round_6_validators:
            earnings = compute_total_earnings(fee_events, addr)
            assert earnings > 0  # Should have received part of the split bond

    def test_max_length_chained_appeals(self):
        """Test maximum realistic chain of unsuccessful appeals."""
        # Create a very long chain (up to the maximum 16 appeals)
        rounds = []

        # Pattern: Normal → Appeal → Normal → Appeal → ... (16 appeals total)
        for i in range(16):
            # Normal round
            normal_round = Round(
                rotations=[
                    Rotation(
                        votes={
                            addresses_pool[i * 10]: ["LEADER_RECEIPT", "AGREE"],
                            addresses_pool[i * 10 + 1]: "AGREE",
                            addresses_pool[i * 10 + 2]: "AGREE",
                            addresses_pool[i * 10 + 3]: "DISAGREE",
                        }
                    )
                ]
            )
            rounds.append(normal_round)

            # Appeal round (all unsuccessful)
            appeal_round = Round(
                rotations=[
                    Rotation(
                        votes={
                            addresses_pool[i * 10 + 4]: "AGREE",
                            addresses_pool[i * 10 + 5]: "AGREE",
                            addresses_pool[i * 10 + 6]: "AGREE",
                            addresses_pool[i * 10 + 7]: "DISAGREE",
                            addresses_pool[i * 10 + 8]: "DISAGREE",
                        }
                    )
                ]
            )
            rounds.append(appeal_round)

        # Final round
        rounds.append(
            Round(
                rotations=[
                    Rotation(
                        votes={
                            addresses_pool[160]: ["LEADER_RECEIPT", "AGREE"],
                            addresses_pool[161]: "AGREE",
                        }
                    )
                ]
            )
        )

        transaction_results = TransactionRoundResults(rounds=rounds)
        labels = label_rounds(transaction_results)

        # Verify all appeals are unsuccessful
        # Count actual appeal labels in the result
        appeal_labels = [
            i
            for i, label in enumerate(labels)
            if "APPEAL" in label
            and label
            not in [
                "SPLIT_PREVIOUS_APPEAL_BOND",
                "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            ]
        ]
        assert len(appeal_labels) == 16  # Should have 16 appeals
        for idx in appeal_labels:
            assert labels[idx] == "APPEAL_VALIDATOR_UNSUCCESSFUL"

        # Verify pattern integrity is maintained throughout
        assert len(labels) == 33  # 16 normal + 16 appeals + 1 final
        assert all(
            label in ["NORMAL_ROUND", "APPEAL_VALIDATOR_UNSUCCESSFUL"]
            for label in labels
        )


class TestChainedAppealsEdgeCases:
    """Edge cases specific to chained appeals."""

    def test_successful_after_unsuccessful_chain(self):
        """Test successful appeal after a chain of unsuccessful ones."""
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 1: First unsuccessful appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[4]: "AGREE",
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 2: Normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[8]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "AGREE",
                                addresses_pool[11]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 3: Second unsuccessful appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[12]: "AGREE",
                                addresses_pool[13]: "AGREE",
                                addresses_pool[14]: "AGREE",
                                addresses_pool[15]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 4: Normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[16]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[17]: "AGREE",
                                addresses_pool[18]: "AGREE",
                                addresses_pool[19]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 5: SUCCESSFUL appeal (validators change their mind)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[20]: "DISAGREE",
                                addresses_pool[21]: "DISAGREE",
                                addresses_pool[22]: "DISAGREE",
                                addresses_pool[23]: "AGREE",
                            }
                        )
                    ]
                ),
                # Round 6: Normal round after successful appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[24]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[25]: "AGREE",
                                addresses_pool[26]: "AGREE",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)

        # First two appeals unsuccessful
        assert labels[1] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert labels[3] == "APPEAL_VALIDATOR_UNSUCCESSFUL"

        # Third appeal successful, triggering skip round
        assert labels[4] == "SKIP_ROUND"  # This should become skip round
        assert labels[5] == "APPEAL_VALIDATOR_SUCCESSFUL"
        assert labels[6] == "NORMAL_ROUND"

    def test_alternating_successful_unsuccessful(self):
        """Test alternating successful and unsuccessful appeals."""
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal round (undetermined for leader appeal)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "DISAGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "TIMEOUT",
                            }
                        )
                    ]
                ),
                # Round 1: Successful leader appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[5]: "NA",
                                addresses_pool[6]: "NA",
                            }
                        )
                    ]
                ),
                # Round 2: Normal round with majority
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[7]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[8]: "AGREE",
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 3: Unsuccessful validator appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[11]: "AGREE",
                                addresses_pool[12]: "AGREE",
                                addresses_pool[13]: "AGREE",
                                addresses_pool[14]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 4: Normal round (undetermined)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[15]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[16]: "AGREE",
                                addresses_pool[17]: "DISAGREE",
                                addresses_pool[18]: "DISAGREE",
                                addresses_pool[19]: "TIMEOUT",
                            }
                        )
                    ]
                ),
                # Round 5: Successful leader appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[20]: "NA",
                                addresses_pool[21]: "NA",
                            }
                        )
                    ]
                ),
                # Round 6: Final round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[22]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[23]: "AGREE",
                                addresses_pool[24]: "AGREE",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)

        # Check alternating pattern
        assert labels[0] == "SKIP_ROUND"  # Due to successful appeal after
        assert labels[1] == "APPEAL_LEADER_SUCCESSFUL"
        assert labels[2] == "NORMAL_ROUND"
        assert labels[3] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert labels[4] == "SKIP_ROUND"  # Due to successful appeal after
        assert labels[5] == "APPEAL_LEADER_SUCCESSFUL"
        assert labels[6] == "NORMAL_ROUND"


def test_invariants_with_chained_appeals():
    """Test that all invariants hold even with chained appeals."""

    # Generate various chained appeal scenarios
    test_scenarios = []

    # Scenario 1: Double chain
    scenario1 = TransactionRoundResults(
        rounds=[
            Round(
                rotations=[
                    Rotation(
                        votes={
                            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                            addresses_pool[1]: "AGREE",
                            addresses_pool[2]: "AGREE",
                        }
                    )
                ]
            ),
            Round(rotations=[Rotation(votes={addresses_pool[3]: "AGREE"})]),
            Round(
                rotations=[
                    Rotation(
                        votes={
                            addresses_pool[4]: ["LEADER_RECEIPT", "AGREE"],
                            addresses_pool[5]: "AGREE",
                        }
                    )
                ]
            ),
            Round(rotations=[Rotation(votes={addresses_pool[6]: "AGREE"})]),
            Round(
                rotations=[
                    Rotation(
                        votes={
                            addresses_pool[7]: ["LEADER_RECEIPT", "AGREE"],
                            addresses_pool[8]: "AGREE",
                        }
                    )
                ]
            ),
        ]
    )
    test_scenarios.append(scenario1)

    # Test all scenarios
    for scenario in test_scenarios:
        labels = label_rounds(scenario)

        # Invariant 1: Every round has a label
        assert len(labels) == len(scenario.rounds)

        # Invariant 2: Appeal labels correspond to appeal rounds
        for i, label in enumerate(labels):
            if "APPEAL" in label and label not in [
                "SPLIT_PREVIOUS_APPEAL_BOND",
                "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            ]:
                # Check that this round has appeal characteristics
                round_obj = scenario.rounds[i]
                if round_obj.rotations:
                    votes = round_obj.rotations[-1].votes
                    # Should have NA votes or no leader receipt
                    has_na_votes = any(
                        v == "NA" or (isinstance(v, list) and "NA" in v)
                        for v in votes.values()
                    )
                    has_leader_receipt = any(
                        isinstance(v, list) and v[0] == "LEADER_RECEIPT"
                        for v in votes.values()
                    )
                    assert has_na_votes or not has_leader_receipt

        # Invariant 3: Valid labels
        valid_labels = {
            "NORMAL_ROUND",
            "EMPTY_ROUND",
            "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
            "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
            "APPEAL_LEADER_SUCCESSFUL",
            "APPEAL_LEADER_UNSUCCESSFUL",
            "APPEAL_VALIDATOR_SUCCESSFUL",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
            "LEADER_TIMEOUT",
            "VALIDATORS_PENALTY_ONLY_ROUND",
            "SKIP_ROUND",
            "LEADER_TIMEOUT_50_PERCENT",
            "SPLIT_PREVIOUS_APPEAL_BOND",
            "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
            "EQUAL_SPLIT",
        }
        assert all(label in valid_labels for label in labels)


if __name__ == "__main__":
    print("Testing chained unsuccessful appeals...")

    test_class = TestChainedUnsuccessfulAppeals()

    print("\n1. Testing double validator unsuccessful appeals...")
    test_class.test_double_validator_unsuccessful_appeal(verbose=True)

    print("\n2. Testing triple chained unsuccessful appeals...")
    test_class.test_triple_chained_unsuccessful_appeals()

    print("\n3. Testing mixed leader/validator unsuccessful chains...")
    test_class.test_mixed_leader_validator_unsuccessful_chain()

    print("\n4. Testing leader timeout unsuccessful chains...")
    test_class.test_leader_timeout_unsuccessful_chain()

    print("\n5. Testing fee distribution with chained appeals...")
    test_class.test_fee_distribution_with_chained_appeals(verbose=True)

    print("\n6. Testing maximum length chains...")
    test_class.test_max_length_chained_appeals()

    print("\n7. Testing edge cases...")
    edge_tests = TestChainedAppealsEdgeCases()
    edge_tests.test_successful_after_unsuccessful_chain()
    edge_tests.test_alternating_successful_unsuccessful()

    print("\n8. Testing invariants hold with chained appeals...")
    test_invariants_with_chained_appeals()

    print("\n✓ All chained appeal tests passed!")
