ETH_ADDRESS_REGEX = r"^0x[a-fA-F0-9]{40}$"

# Normal round sizes (for even-indexed rounds: 0, 2, 4, ...)
NORMAL_ROUND_SIZES = [
    5,  # Round 0
    11,  # Round 2
    23,  # Round 4
    47,  # Round 6
    95,  # Round 8
    191,  # Round 10
    383,  # Round 12
    767,  # Round 14
    1000,  # Round 16+
]

# Appeal round sizes (for odd-indexed rounds: 1, 3, 5, ...)
APPEAL_ROUND_SIZES = [
    7,  # Round 1 (appeal 0)
    13,  # Round 3 (appeal 1)
    25,  # Round 5 (appeal 2)
    49,  # Round 7 (appeal 3)
    97,  # Round 9 (appeal 4)
    193,  # Round 11 (appeal 5)
    385,  # Round 13 (appeal 6)
    769,  # Round 15 (appeal 7)
    1000,  # Round 17+ (appeal 8+)
]

PENALTY_REWARD_COEFFICIENT = 1

# Multiple of the appeal bond returned to a successful appellant:
# principal (1.0) plus profit (APPEAL_REWARD_MULTIPLE - 1.0). Keep this value
# in lockstep with the corresponding FeesProcessor constant.
APPEAL_REWARD_MULTIPLE = 2.5

DEFAULT_HASH = "0xdefault"
DEFAULT_STAKE = 2000000

IDLE_PENALTY_COEFFICIENT = 0.01
DETERMINISTIC_VIOLATION_PENALTY_COEFFICIENT = 0.1
