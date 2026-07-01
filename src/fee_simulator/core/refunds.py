from typing import List
from src.fee_simulator.protocol.models import FeeEvent, TransactionBudget
from src.fee_simulator.display.fee_distribution import display_fee_distribution
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.utils import is_appeal_round, compute_total_cost
from src.fee_simulator.utils_round_sizes import find_previous_normal_round


def compute_sender_refund(
    sender_address: str,
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
) -> float:
    """
    Mirror the contract's settlement (FeeManagerHelpers.finalizeFeesDistribution):
    the sender receives whatever is left of the fee pot after every credit.

    Conservation over the fee pot:
      money in  = total_cost (sender) + appeal bonds (appellants)
      money out = every `earned` credit (validators, leaders, appellant
                  rewards, explicit sender legs) + residual appellant bond
                  burns (paths where the simulator still destroys a bond)
                  + this refund

    ⇒ refund = total_cost + Σ bonds − Σ earned − Σ appellant burns

    Division remainders are never credited to anyone, so they flow back to
    the sender automatically — same as the contract's leftOverFees.

    Note: `burned` on VALIDATOR events is a stake-level penalty, not a fee
    pot flow, so it does not participate here. Only APPEALANT burns (bond
    value the simulator destroys on fallback paths) reduce the pot.
    """
    # TODO: when introducing toppers, we need to change this function

    total_cost = compute_total_cost(transaction_budget)

    # Bonds paid into the pot by appellants, one per appeal round
    bonds_total = 0
    for i, label in enumerate(round_labels):
        if not is_appeal_round(label):
            continue
        normal_round_index = find_previous_normal_round(i, round_labels)
        if normal_round_index is None:
            normal_round_index = max(i - 1, 0)
        bonds_total += compute_appeal_bond(
            normal_round_index=normal_round_index,
            leader_timeout=transaction_budget.leaderTimeout,
            validators_timeout=transaction_budget.validatorsTimeout,
            round_labels=round_labels,
            appeal_round_index=i,
            rotations=transaction_budget.rotations,
        )

    earned_total = 0
    appellant_burns = 0
    for event in fee_events:
        earned_total += event.earned
        if event.role == "APPEALANT":
            appellant_burns += event.burned

    refund = total_cost + bonds_total - earned_total - appellant_burns

    if refund < 0:
        display_fee_distribution(fee_events)
        raise ValueError(
            f"Fee pot overdrawn: credits ({earned_total + appellant_burns}) exceed "
            f"pot ({total_cost + bonds_total})"
        )

    return refund
