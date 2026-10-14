"""Deterministic replay vectors consumed by consensus regression tests."""
from src.fee_simulator.protocol.models import Rotation, Round, TransactionRoundResults, TransactionBudget
from src.fee_simulator.core.transaction_processing import process_transaction


def recompute_vectors():
    addresses = [f"0x{i:040x}" for i in range(1, 8)]
    votes = {a: (["LEADER_RECEIPT", "AGREE"] if i == 0 else "AGREE") for i, a in enumerate(addresses[:5])}
    generation = TransactionRoundResults(rounds=[Round(rotations=[Rotation(votes=votes)])])
    cases = []
    for retries in range(3):
        budget = TransactionBudget(leaderTimeout=100, validatorsTimeout=200, appealRounds=0,
                                   rotations=[retries], senderAddress=addresses[-1])
        events, _ = process_transaction(addresses, generation, budget, [generation] * retries)
        cases.append({
            "assignedRotations": retries,
            "completedGenerations": retries + 1,
            "leaderTimeUnits": budget.leaderTimeout,
            "validatorTimeUnits": budget.validatorsTimeout,
            "validators": 5,
            "totalWork": sum(e.earned for e in events if e.role in ("LEADER", "VALIDATOR")),
            "senderRefund": sum(e.earned for e in events if e.role == "SENDER"),
            "nextRecompute": "Canceled",
        })
    return {"schemaVersion": 1, "funding": "sender-assigned-rotations", "cases": cases}
