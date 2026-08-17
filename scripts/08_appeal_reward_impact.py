"""Appeal-reward-multiple impact demo.

Runs a fixed set of transaction paths through the simulator and prints, per
scenario, what the sender actually pays and what a successful appellant nets.
Reads the appeal reward multiple from protocol.constants.APPEAL_REWARD_MULTIPLE
and separately reports the sender cost added by original-round vindication:

    PYTHONPATH=. python scripts/08_appeal_reward_impact.py

Units follow the repo test convention (validatorsTimeout=200, leaderTimeout=100).
"""

from src.fee_simulator.protocol.constants import APPEAL_REWARD_MULTIPLE
from src.fee_simulator.core.majority import compute_majority, normalize_vote
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.utils import compute_total_cost, generate_random_eth_address
from src.fee_simulator.utils_round_sizes import find_previous_normal_round
from src.fee_simulator.metrics.address_metrics import (
    compute_total_earnings,
    compute_total_costs,
)

L, V = 100, 200
pool = [generate_random_eth_address() for _ in range(2000)]
sender, appealant = pool[1999], pool[23]

SCENARIOS = {
    "no_appeal": ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
    "validator_appeal_SUCCESS": [
        "START",
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "VALIDATOR_APPEAL_SUCCESSFUL",
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "END",
    ],
    "validator_appeal_FAIL": [
        "START",
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "VALIDATOR_APPEAL_UNSUCCESSFUL",
        "END",
    ],
    "leader_appeal_SUCCESS": [
        "START",
        "LEADER_RECEIPT_MAJORITY_DISAGREE",
        "LEADER_APPEAL_SUCCESSFUL",
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "END",
    ],
}


def compute_vindication_impact(tx_results, labels) -> tuple[int, int]:
    vindicated_count = 0
    for round_index, label in enumerate(labels):
        if label != "APPEAL_VALIDATOR_SUCCESSFUL":
            continue

        appeal_round = tx_results.rounds[round_index]
        if not appeal_round.rotations:
            continue
        new_majority = compute_majority(appeal_round.rotations[-1].votes)
        if new_majority == "UNDETERMINED":
            continue

        original_round_index = find_previous_normal_round(round_index, labels)
        if original_round_index is None:
            continue
        original_round = tx_results.rounds[original_round_index]
        if not original_round.rotations:
            continue

        vindicated_count += sum(
            normalize_vote(vote) == new_majority
            for vote in original_round.rotations[-1].votes.values()
        )

    return vindicated_count, vindicated_count * V


def main() -> None:
    print(f"APPEAL_REWARD_MULTIPLE = {APPEAL_REWARD_MULTIPLE}  (V={V}, L={L})\n")
    header = (
        f"{'scenario':30} {'upfront_deposit':>15} {'sender_realized':>15} "
        f"{'vindicated':>10} {'added_user_cost':>15} {'appellant_net':>13}"
    )
    print(header)
    print("-" * len(header))
    for name, path in SCENARIOS.items():
        tx_results, budget = path_to_transaction_results(
            path=path,
            addresses=pool,
            sender_address=sender,
            appealant_address=appealant,
            leader_timeout=L,
            validators_timeout=V,
        )
        fee_events, labels = process_transaction(
            addresses=pool,
            transaction_results=tx_results,
            transaction_budget=budget,
        )
        upfront = compute_total_cost(budget)
        sender_realized = compute_total_costs(
            fee_events, sender
        ) - compute_total_earnings(fee_events, sender)
        appellant_net = compute_total_earnings(
            fee_events, appealant
        ) - compute_total_costs(fee_events, appealant)
        vindicated_count, vindication_cost = compute_vindication_impact(
            tx_results, labels
        )
        print(
            f"{name:30} {upfront:>15} {sender_realized:>15} "
            f"{vindicated_count:>10} {vindication_cost:>15} {appellant_net:>13}"
        )


if __name__ == "__main__":
    main()
