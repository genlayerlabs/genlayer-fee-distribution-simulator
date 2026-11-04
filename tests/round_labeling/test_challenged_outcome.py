import pytest
from src.fee_simulator.protocol.models import Round, TransactionRoundResults
from src.fee_simulator.core.round_labeling import label_rounds


@pytest.mark.parametrize("challenged", ["AGREE", "TIMEOUT"])
@pytest.mark.parametrize("outcome", ["AGREE", "TIMEOUT", "UNDETERMINED", None])
@pytest.mark.parametrize("voided", [False, True])
def test_jury_uses_admission_basis(challenged, outcome, voided):
    # The earlier jury has no raw result; the actual challenged outcome is
    # frozen independently. Deadline and revealed tallies use the same rule.
    rounds = [Round(rotations=[]), Round(rotations=[]), Round(rotations=[]),
              Round(rotations=[], challenged_outcome=challenged,
                    settled_outcome=outcome, appeal_voided=voided)]
    label = label_rounds(TransactionRoundResults(rounds=rounds))[3]
    success = outcome is not None and outcome != challenged and not voided
    assert label == ("APPEAL_VALIDATOR_SUCCESSFUL" if success
                     else "APPEAL_VALIDATOR_UNSUCCESSFUL")
