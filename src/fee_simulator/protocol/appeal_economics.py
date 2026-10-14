from fractions import Fraction


SUCCESS_REWARD_NUMERATOR = 5
SUCCESS_REWARD_DENOMINATOR = 2
APPEAL_REWARD_MULTIPLE = Fraction(
    SUCCESS_REWARD_NUMERATOR, SUCCESS_REWARD_DENOMINATOR
)


def successful_appeal_reward(appeal_bond: int) -> int:
    """Return principal plus profit using Solidity's integer division."""
    return appeal_bond * SUCCESS_REWARD_NUMERATOR // SUCCESS_REWARD_DENOMINATOR


def successful_appeal_profit(appeal_bond: int) -> int:
    return successful_appeal_reward(appeal_bond) - appeal_bond
