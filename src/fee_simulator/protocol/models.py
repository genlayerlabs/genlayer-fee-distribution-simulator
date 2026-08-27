import re
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator

from src.fee_simulator.protocol.constants import ETH_ADDRESS_REGEX
from src.fee_simulator.protocol.types import RoundLabel, Vote, Role


class EventSequence:
    """
    Manages an auto-incrementing sequence counter for FeeEvent IDs.
    """

    def __init__(self):
        self._counter = 1

    def set_counter(self, counter: int):
        self._counter = counter

    def next_id(self) -> int:
        current = self._counter
        self._counter += 1
        return current


class Appeal(BaseModel):
    model_config = ConfigDict(frozen=True)
    appealantAddress: str

    @field_validator("appealantAddress")
    def validate_address(cls, v):
        if not re.match(ETH_ADDRESS_REGEX, v):
            raise ValueError(f"Invalid Ethereum address: {v}")
        return v


class Rotation(BaseModel):
    model_config = ConfigDict(frozen=True)
    votes: Dict[str, Vote]
    reserve_votes: Dict[str, Vote] = {}

    @field_validator("votes")
    def validate_vote_addresses(cls, v):
        for addr in v.keys():
            if not re.match(ETH_ADDRESS_REGEX, addr):
                raise ValueError(f"Invalid Ethereum address: {addr}")
        return v

    @field_validator("reserve_votes")
    def validate_reserve_addresses(cls, v):
        for addr in v.keys():
            if not re.match(ETH_ADDRESS_REGEX, addr):
                raise ValueError(f"Invalid reserve Ethereum address: {addr}")
        return v

    @field_validator("votes")
    def validate_vote_hashes(cls, v):
        for addr, vote in v.items():
            if isinstance(vote, list) and len(vote) > 1:
                # Check if last element is a hash
                if len(vote) == 3 or (
                    len(vote) == 2
                    and vote[0] not in ["LEADER_RECEIPT", "LEADER_TIMEOUT"]
                ):
                    hash_value = vote[-1]
                    if not re.match(r"^0x[a-fA-F0-9]+$", hash_value):
                        raise ValueError(
                            f"Invalid hash format for address {addr}: {hash_value}"
                        )
        return v


class Round(BaseModel):
    model_config = ConfigDict(frozen=True)
    rotations: List[Rotation]


class TransactionRoundResults(BaseModel):
    model_config = ConfigDict(frozen=True)
    rounds: List[Round]


class FeeEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    sequence_id: int
    address: str
    round_index: Optional[int] = None
    round_label: Optional[RoundLabel] = None
    role: Optional[Role] = None
    vote: Optional[Vote] = None
    hash: Optional[str] = None
    cost: int = Field(default=0, ge=0)
    staked: int = Field(default=0, ge=0)
    earned: int = Field(default=0, ge=0)
    slashed: int = Field(default=0, ge=0)
    burned: int = Field(default=0, ge=0)  # penalty


class TransactionBudget(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    leaderTimeout: int = Field(ge=0)
    validatorsTimeout: int = Field(ge=0)
    appealRounds: int = Field(ge=0)
    # Funded rotation allowance for each normal round. Consensus seeds one
    # common runtime capacity from the minimum entry in this schedule.
    rotations: List[int]
    # Rotations actually consumed in each normal round. Kept separate from the
    # funded allowance because LeaderTimeout bonds use the live remainder while
    # Undetermined bonds use a future configured schedule entry.
    rotationsUsed: Optional[List[int]] = None
    senderAddress: str
    appeals: Optional[List[Appeal]] = []
    staking_distribution: Literal["constant", "normal"] = Field(default="constant")
    staking_mean: Optional[float] = Field(default=None, ge=0)
    staking_variance: Optional[float] = Field(default=None, ge=0)

    @field_validator("senderAddress")
    def validate_sender_address(cls, v):
        if not re.match(ETH_ADDRESS_REGEX, v):
            raise ValueError(f"Invalid sender Ethereum address: {v}")
        return v

    @model_validator(mode="after")
    def validate_rotations(self):
        # Rotations are indexed by normal round index, so we just need at least one
        if len(self.rotations) == 0:
            raise ValueError("Must have at least one rotation")
        if self.rotationsUsed is not None and len(self.rotationsUsed) != len(
            self.rotations
        ):
            raise ValueError("rotationsUsed must align with rotations")
        return self

    @model_validator(mode="after")
    def validate_staking_params(self):
        if self.staking_distribution == "normal":
            if self.staking_mean is None or self.staking_variance is None:
                raise ValueError(
                    "staking_mean and staking_variance must be provided for normal distribution"
                )
        if self.staking_distribution == "constant" and (
            self.staking_mean is not None or self.staking_variance is not None
        ):
            raise ValueError(
                "staking_mean and staking_variance should not be provided for constant distribution"
            )
        return self
