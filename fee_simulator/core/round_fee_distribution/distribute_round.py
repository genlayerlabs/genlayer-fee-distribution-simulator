from typing import Callable, Dict, List

from fee_simulator.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)

from fee_simulator.types import (
    RoundLabel,
)

from fee_simulator.core.round_fee_distribution import (
    apply_normal_round,
    apply_appeal_leader_timeout_successful,
    apply_appeal_leader_successful,
    apply_appeal_validator_successful,
    apply_appeal_validator_unsuccessful,
    apply_leader_timeout_50_percent,
    apply_split_previous_appeal_bond,
    apply_leader_timeout_50_previous_appeal_bond,
    apply_leader_timeout_150_previous_normal_round,
)

FeeTransformer = Callable[[TransactionRoundResults, int, TransactionBudget, EventSequence], List[FeeEvent]]

FEE_RULES: Dict[RoundLabel, FeeTransformer] = {
    "NORMAL_ROUND": apply_normal_round,
    "EMPTY_ROUND": lambda r, i, b, s: [],
    "SKIP_ROUND": lambda r, i, b, s: [],
    "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL":  lambda r, i, b, s: [],
    "APPEAL_LEADER_TIMEOUT_SUCCESSFUL": apply_appeal_leader_timeout_successful,
    "APPEAL_LEADER_SUCCESSFUL": apply_appeal_leader_successful,
    "APPEAL_LEADER_UNSUCCESSFUL":  lambda r, i, b, s: [],
    "APPEAL_VALIDATOR_SUCCESSFUL": apply_appeal_validator_successful,
    "APPEAL_VALIDATOR_UNSUCCESSFUL": apply_appeal_validator_unsuccessful,
    "LEADER_TIMEOUT_50_PERCENT": apply_leader_timeout_50_percent,
    "SPLIT_PREVIOUS_APPEAL_BOND": apply_split_previous_appeal_bond,
    "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND": apply_leader_timeout_50_previous_appeal_bond,
    "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND": apply_leader_timeout_150_previous_normal_round,
}

def distribute_round(
    transaction_results: TransactionRoundResults,
    round_index: int,
    label: RoundLabel,
    budget: TransactionBudget,
    event_sequence: EventSequence
) -> List[FeeEvent]:
    """
    Distribute fees for a single round based on its label, generating FeeEvent instances.
    """
    transformer = FEE_RULES.get(label, lambda r, i, b, s: [])
    return transformer(transaction_results, round_index, budget, event_sequence)