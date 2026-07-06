"""Appeal-reward-multiple impact demo.

Runs a fixed set of transaction paths through the simulator and prints, per
scenario, what the sender actually pays and what a successful appellant nets.
Reads the appeal reward multiple from protocol.constants.APPEAL_REWARD_MULTIPLE,
so you can compare regimes by flipping that one value:

    # edit src/fee_simulator/protocol/constants.py:
    #   APPEAL_REWARD_MULTIPLE = 1.5   (then 2.5)
    PYTHONPATH=. python scripts/08_appeal_reward_impact.py

Units follow the repo test convention (validatorsTimeout=200, leaderTimeout=100).
"""

from src.fee_simulator.protocol.constants import APPEAL_REWARD_MULTIPLE
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.utils import compute_total_cost, generate_random_eth_address
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
        "START", "LEADER_RECEIPT_MAJORITY_AGREE",
        "VALIDATOR_APPEAL_SUCCESSFUL", "LEADER_RECEIPT_MAJORITY_AGREE", "END",
    ],
    "validator_appeal_FAIL": [
        "START", "LEADER_RECEIPT_MAJORITY_AGREE",
        "VALIDATOR_APPEAL_UNSUCCESSFUL", "END",
    ],
    "leader_appeal_SUCCESS": [
        "START", "LEADER_RECEIPT_MAJORITY_DISAGREE",
        "LEADER_APPEAL_SUCCESSFUL", "LEADER_RECEIPT_MAJORITY_AGREE", "END",
    ],
}


def main() -> None:
    print(f"APPEAL_REWARD_MULTIPLE = {APPEAL_REWARD_MULTIPLE}  (V={V}, L={L})\n")
    header = f"{'scenario':30} {'upfront_deposit':>15} {'sender_realized':>15} {'appellant_net':>13}"
    print(header)
    print("-" * len(header))
    for name, path in SCENARIOS.items():
        tx_results, budget = path_to_transaction_results(
            path=path, addresses=pool, sender_address=sender,
            appealant_address=appealant, leader_timeout=L, validators_timeout=V,
        )
        label_rounds(tx_results)
        fee_events, _ = process_transaction(
            addresses=pool, transaction_results=tx_results, transaction_budget=budget,
        )
        upfront = compute_total_cost(budget)
        sender_realized = compute_total_costs(fee_events, sender) - compute_total_earnings(fee_events, sender)
        appellant_net = compute_total_earnings(fee_events, appealant) - compute_total_costs(fee_events, appealant)
        print(f"{name:30} {upfront:>15} {sender_realized:>15} {appellant_net:>13}")


if __name__ == "__main__":
    main()
