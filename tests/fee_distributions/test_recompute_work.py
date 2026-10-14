"""Sender-assigned rotations fund replay; invalidation does not erase work."""
import pytest
from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.bond_computing import compute_appeal_bond

ADDRESSES = [f"0x{i:040x}" for i in range(1, 201)]


def accepted(rotations=0):
    result, budget = path_to_transaction_results(
        ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"], ADDRESSES,
        sender_address=ADDRESSES[-1], appealant_address=ADDRESSES[-2],
        leader_timeout=100, validators_timeout=200,
        rotation_counts={0: rotations},
    )
    # The regression compares five unanimous seats, including the leader.
    votes = result.rounds[0].rotations[-1].votes
    for i, address in enumerate(votes):
        votes[address] = ["LEADER_RECEIPT", "AGREE"] if i == 0 else "AGREE"
    return result, budget


@pytest.mark.parametrize("retries", [0, 1, 2])
def test_replays_preserve_full_work_and_share_sender_allowance(retries):
    result, budget = accepted()
    budget = budget.model_copy(update={"rotations": [retries]})
    events, _ = process_transaction(ADDRESSES, result, budget, [result] * retries)
    work = sum(e.earned for e in events if e.role in ("LEADER", "VALIDATOR"))
    assert work == 1100 * (retries + 1)
    assert sum(e.cost for e in events) == sum(e.earned for e in events)
    with pytest.raises(ValueError, match="assigned rotations"):
        process_transaction(ADDRESSES, result, budget, [result] * (retries + 1))


def test_real_rotation_and_replay_consume_same_allowance():
    historical, _ = accepted()
    current, budget = accepted(rotations=1)
    with pytest.raises(ValueError, match="assigned rotations"):
        process_transaction(ADDRESSES, current, budget, [historical])
    events, _ = process_transaction(
        ADDRESSES, current, budget.model_copy(update={"rotations": [2]}), [historical]
    )
    assert sum(e.earned for e in events if e.role in ("LEADER", "VALIDATOR")) == 2250


def test_invalidated_bond_principal_is_not_spendable():
    labels = ["NORMAL_ROUND", "APPEAL_VALIDATOR_UNSUCCESSFUL"]
    assert compute_appeal_bond(0, 100, 200, labels, appeal_round_index=1) > 0
    assert compute_appeal_bond(0, 100, 200, labels, appeal_round_index=1, invalidated_generation=True) == 0
