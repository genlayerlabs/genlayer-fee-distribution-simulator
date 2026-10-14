"""Two supplied corrective outcomes under the opt-in proposal; no network I/O.

Run from the repository root: python -m examples.owner_funded_fees
Amounts and admission limits are illustrative, not network recommendations.
"""

import json

from src.fee_simulator.core.owner_liability import (
    OwnerCapital, TransactionCase, WorkCommitment, WorkKey, simulate_owner_funded_fees,
)
from src.fee_simulator.protocol.models import (
    Appeal, Rotation, Round, TransactionBudget, TransactionRoundResults,
)


def example(kind):
    addresses = tuple(f"0x{i:040x}" for i in range(1, 31))
    source = {actor: "DISAGREE" for actor in addresses[:5]}
    source[addresses[0]] = ["LEADER_RECEIPT", "AGREE"]
    replacement = addresses[5:16]
    if kind == "timeout":
        source = {actor: "NA" for actor in addresses[:5]}
        source[addresses[0]] = ["LEADER_TIMEOUT", "NA"]
        replacement = addresses[1:5]
    new_votes = {actor: "AGREE" for actor in replacement}
    new_votes[replacement[0]] = ["LEADER_RECEIPT", "AGREE"]
    results = TransactionRoundResults(rounds=[
        Round(rotations=[Rotation(votes=source)]),
        Round(rotations=[Rotation(votes={actor: "NA" for actor in addresses[5:12]})]),
        Round(rotations=[Rotation(votes=new_votes)]),
    ])
    budget = TransactionBudget(
        leaderTimeout=100, validatorsTimeout=200, appealRounds=1, rotations=[0, 0],
        senderAddress=addresses[-1], appeals=[Appeal(appealantAddress=addresses[-2])],
    )
    case = TransactionCase(kind, addresses, results, budget)
    # Selection identities plus externally declared workload ceilings. No cap
    # is calculated from the settlement's realized fees or eventual success.
    plans = tuple(
        WorkCommitment(WorkKey(kind, 0, round_index, actor), actor,
                       negative_fee_cap=200, correction_bonus_cap=5000,
                       other_gain_bound=100)
        for round_index, votes in ((0, source), (2, new_votes))
        for actor, vote in votes.items() if vote != "NA"
    )
    accounts = tuple(OwnerCapital(owner, 50_000, delegated_funds=1_000_000)
                     for owner in sorted({plan.owner for plan in plans}))
    settlement = simulate_owner_funded_fees([case], capital=accounts, commitments=plans)
    tx = settlement.transactions[0]
    source_charge = next(c for c in settlement.charges if c.key.round_index == 0 and c.key.validator == addresses[0])
    source_before = next(a for a in accounts if a.owner == addresses[0])
    source_after = next(a for a in settlement.closing_capital if a.owner == addresses[0])
    return {
        "case": kind,
        "scope": "supplied canonical outcome; illustrative admission caps and G=100",
        "appealBond": tx.corrections[0].bond,
        "netAppealBonus": source_charge.correction_bonus,
        "declaredOtherGainBound": source_charge.other_gains,
        "collectedOwnerPenalty": source_charge.collected,
        "sourceOwnerFundsBefore": source_before.self_funds,
        "sourceOwnerFundsAfter": source_after.self_funds,
        "delegatedFundsBefore": source_before.delegated_funds,
        "delegatedFundsAfter": source_after.delegated_funds,
        "existingPaymentsUnchanged": tx.fee_events[:-1] == tx.ordinary.fee_events,
        "invariants": "passed",
    }


if __name__ == "__main__":
    print(json.dumps({"policy": "opt-in-owner-funded-negative-fees-v1",
                      "cases": [example("leader"), example("timeout")]}, indent=2))
