from src.fee_simulator.specification.state_machine.graph import is_protocol_valid_path


def test_successful_validator_appeal_allows_one_terminal_normal_round():
    assert is_protocol_valid_path(
        [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_UNDETERMINED",
            "END",
        ]
    )


def test_terminal_normal_decision_cannot_reopen_the_appeal_ladder():
    assert not is_protocol_valid_path(
        [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_UNDETERMINED",
            "LEADER_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]
    )
