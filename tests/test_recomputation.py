import pytest

from src.fee_simulator.core.recomputation import RecomputationLedger
from src.fee_simulator.protocol.models import Round, Rotation, TransactionBudget


def accepted(offset=1):
    addresses = [f"0x{n:040x}" for n in range(offset, offset + 5)]
    return Rotation(votes={addresses[0]: ["LEADER_RECEIPT", "AGREE"], **{a: "AGREE" for a in addresses[1:]}})


def ledger(rotations):
    return RecomputationLedger(TransactionBudget(
        leaderTimeout=100, validatorsTimeout=200, appealRounds=0,
        rotations=[rotations], senderAddress=f"0x{100:040x}",
    ), ["A", "B"])


@pytest.mark.parametrize("rotations", [0, 1, 2, 5])
def test_each_recomputation_preserves_honest_work_and_spends_one_retry(rotations):
    model = ledger(rotations)
    for generation in range(rotations + 1):
        model.complete_generation(Round(rotations=[accepted()]))
        model.invalidate("B", generation + 1)
        assert model.consumed == 1100 * (generation + 1)
        if generation < rotations:
            assert model.state == "Invalidated"
            with pytest.raises(ValueError):
                model.finalize()
            model.resume()
            model.resume()
            assert model.rotations_left == rotations - generation - 1
    assert model.state == "Canceled"
    assert model.refund == 0
    assert model.entitlements[f"0x{1:040x}"] == 300 * (rotations + 1)
    with pytest.raises(ValueError):
        model.resume()


def test_a_b_c_historical_reproducer_with_real_rotation():
    model = ledger(2)
    model.complete_generation(Round(rotations=[accepted()]))
    model.invalidate("B", 1)
    model.invalidate("B", 1)
    model.resume()
    votes = accepted().votes.copy()
    keys = list(votes)
    for key in keys[1:]:
        votes[key] = "DISAGREE"
    model.complete_generation(Round(rotations=[Rotation(votes=votes), accepted(6)]))
    assert model.rotations_left == 0
    assert model.consumed == 3050
    model.invalidate("A", 1)
    assert model.state == "Canceled"
    assert model.deposited == 3300
    assert model.refund == 250
    assert [item["earned"] for item in model.history] == [1100, 1950]


def test_normal_finalization_keeps_all_generations_and_refunds_only_unused_budget():
    model = ledger(2)
    model.complete_generation(Round(rotations=[accepted()]))
    model.invalidate("B", 1)
    model.resume()
    model.complete_generation(Round(rotations=[accepted(6)]))
    with pytest.raises(ValueError):
        _ = model.refund
    model.finalize()
    model.finalize()
    assert model.consumed == 2200
    assert model.refund == 1100
    with pytest.raises(ValueError):
        model.invalidate("A", 1)


def test_unfunded_rotation_and_unrelated_invalidation_are_rejected():
    model = ledger(0)
    with pytest.raises(ValueError):
        model.complete_generation(Round(rotations=[accepted(), accepted(6)]))
    assert model.state == "Proposing"
    assert model.consumed == 0
    model.complete_generation(Round(rotations=[accepted()]))
    with pytest.raises(ValueError):
        model.invalidate("unrelated", 1)
    assert model.state == "Accepted"


@pytest.mark.parametrize("rotations", [0, 1])
@pytest.mark.parametrize("reveals", [0, 1, 2, 4])
def test_partial_captures_keep_completed_duties_without_a_failed_leader_discount(rotations, reveals):
    model = ledger(rotations)
    addresses = list(accepted().votes)
    model.record_partial_generation(addresses[0], addresses[1:1 + reveals])
    model.invalidate("A", 1)
    assert model.consumed == 100 + reveals * 200
    if rotations:
        model.resume()
        model.complete_generation(Round(rotations=[accepted()]))
        model.finalize()
        assert model.consumed == 1200 + reveals * 200
    else:
        assert model.state == "Canceled"
    assert model.deposited == model.consumed + model.refund
    assert model.entitlements[addresses[0]] == (400 if rotations else 100)
