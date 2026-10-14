from src.fee_simulator.core.majority import who_is_in_vote_majority


def test_vote_minority_preserves_committee_order():
    rotation = {
        "leader": ["LEADER_RECEIPT", "AGREE"],
        "minority-1": "DISAGREE",
        "majority": "AGREE",
        "minority-2": "TIMEOUT",
    }

    majority, minority = who_is_in_vote_majority(rotation, "AGREE")

    assert majority == ["leader", "majority"]
    assert minority == ["minority-1", "minority-2"]
