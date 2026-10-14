from src.fee_simulator.protocol.appeal_economics import (
    APPEAL_REWARD_MULTIPLE,
    successful_appeal_profit,
    successful_appeal_reward,
)


def test_successful_appeal_economics_are_exact_integer_math():
    bond = 10**30 + 1
    assert APPEAL_REWARD_MULTIPLE.numerator == 5
    assert APPEAL_REWARD_MULTIPLE.denominator == 2
    assert successful_appeal_reward(bond) == bond * 5 // 2
    assert successful_appeal_profit(bond) == bond * 5 // 2 - bond
