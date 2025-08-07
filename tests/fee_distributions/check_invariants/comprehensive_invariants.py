"""
Comprehensive invariant checks for the fee distribution system.
Based on the invariants defined in INVARIANTS_DESIGN.md
"""

from typing import List, Tuple
from fee_simulator.models import FeeEvent, TransactionBudget, TransactionRoundResults
from fee_simulator.types import RoundLabel

# Import all invariant check functions from the invariants module
from tests.fee_distributions.check_invariants.invariants import (
    check_conservation_of_value,
    check_appeal_bond_coverage,
    check_majority_minority_consistency,
    check_sequential_processing,
    check_appeal_follows_normal,
    check_burn_non_negativity,
    check_refund_non_negativity,
    check_vote_consistency,
    check_idle_slashing,
    check_deterministic_violation_slashing,
    check_leader_timeout_earning,
    check_appeal_bond_consistency,
    check_round_size_consistency,
    check_round_label_validity,
    check_appellant_consistency,
    check_no_double_penalties,
    check_bounded_slashing_impact,
    check_no_profit_from_griefing,
    check_cost_of_contention,
    check_progress_monotonicity,
    check_resource_pool_integrity,
    check_irreversibility_of_finality,
    check_temporal_event_consistency,
    check_griefing_amplification,
    InvariantViolation,
)


def check_all_invariants(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel],
    tolerance: int = 10,
) -> Tuple[bool, List[str]]:
    """
    Check all invariants and return (success, list_of_violations)
    """
    violations = []

    invariant_checks = [
        (
            "conservation_of_value",
            lambda: check_conservation_of_value(
                fee_events, transaction_budget, round_labels, tolerance
            ),
        ),
        (
            "appeal_bond_coverage",
            lambda: check_appeal_bond_coverage(
                fee_events, transaction_budget, transaction_results, round_labels
            ),
        ),
        (
            "majority_minority_consistency",
            lambda: check_majority_minority_consistency(
                fee_events, transaction_results, transaction_budget, round_labels
            ),
        ),
        ("sequential_processing", lambda: check_sequential_processing(fee_events)),
        ("appeal_follows_normal", lambda: check_appeal_follows_normal(round_labels)),
        ("round_label_validity", lambda: check_round_label_validity(round_labels)),
        (
            "appellant_consistency",
            lambda: check_appellant_consistency(
                fee_events, transaction_budget, round_labels
            ),
        ),
        ("burn_non_negativity", lambda: check_burn_non_negativity(fee_events)),
        ("no_double_penalties", lambda: check_no_double_penalties(fee_events)),
        ("bounded_slashing_impact", lambda: check_bounded_slashing_impact(fee_events)),
        (
            "no_profit_from_griefing",
            lambda: check_no_profit_from_griefing(
                fee_events, transaction_results, round_labels
            ),
        ),
        (
            "cost_of_contention",
            lambda: check_cost_of_contention(fee_events, round_labels),
        ),
        (
            "griefing_amplification",
            lambda: check_griefing_amplification(fee_events, round_labels),
        ),
        (
            "progress_monotonicity",
            lambda: check_progress_monotonicity(
                transaction_results, fee_events, round_labels
            ),
        ),
        (
            "resource_pool_integrity",
            lambda: check_resource_pool_integrity(
                transaction_results, fee_events, transaction_budget
            ),
        ),
        (
            "irreversibility_of_finality",
            lambda: check_irreversibility_of_finality(
                transaction_results, fee_events, round_labels
            ),
        ),
        (
            "temporal_event_consistency",
            lambda: check_temporal_event_consistency(fee_events),
        ),
        (
            "refund_non_negativity",
            lambda: check_refund_non_negativity(
                fee_events, transaction_budget, round_labels
            ),
        ),
        (
            "vote_consistency",
            lambda: check_vote_consistency(fee_events, transaction_results),
        ),
        ("idle_slashing", lambda: check_idle_slashing(fee_events)),
        (
            "deterministic_violation_slashing",
            lambda: check_deterministic_violation_slashing(fee_events),
        ),
        (
            "leader_timeout_earning",
            lambda: check_leader_timeout_earning(
                fee_events, transaction_budget, round_labels
            ),
        ),
        (
            "appeal_bond_consistency",
            lambda: check_appeal_bond_consistency(
                fee_events, transaction_budget, round_labels
            ),
        ),
        (
            "round_size_consistency",
            lambda: check_round_size_consistency(
                fee_events, transaction_results, round_labels
            ),
        ),
    ]

    for invariant_name, check_func in invariant_checks:
        try:
            check_func()
        except InvariantViolation as e:
            violations.append(f"{e.invariant_name}: {e.message}")
        except Exception as e:
            violations.append(f"{invariant_name}: Unexpected error - {str(e)}")

    return len(violations) == 0, violations


# Backward compatibility wrapper
def check_comprehensive_invariants(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel],
    tolerance: int = 10,
) -> None:
    """
    Wrapper that raises exception on first violation for backward compatibility
    """
    success, violations = check_all_invariants(
        fee_events, transaction_budget, transaction_results, round_labels, tolerance
    )

    if not success:
        raise AssertionError(f"Invariant violations found:\n" + "\n".join(violations))
