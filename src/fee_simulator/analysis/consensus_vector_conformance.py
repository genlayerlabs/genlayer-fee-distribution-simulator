"""Classify the intentional delta between consensus and future fee vectors.

The Solidity repository already treats its checked-in simulator vectors as an
executable oracle.  This module keeps that bridge intact: it compares those
contract-conformant vectors with vectors emitted by the current simulator and
accepts only the two pending economic changes:

* 2.5x, rather than 1.5x, return of a successful appeal bond; and
* one validator-timeout credit for each original voter vindicated by a clear
  successful validator appeal.

The sender-refund difference is checked as the conservation consequence of
the larger upfront reserve and the two payout changes.  It is not classified
as an independent protocol change.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
import json

from src.fee_simulator.protocol.constants import NORMAL_ROUND_SIZES


SUCCESSFUL_APPEAL_TYPES = {
    "VALIDATOR_APPEAL_SUCCESSFUL",
    "LEADER_APPEAL_SUCCESSFUL",
    "LEADER_TIMEOUT_APPEAL_SUCCESSFUL",
}
UNSUCCESSFUL_APPEAL_TYPES = {
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "LEADER_APPEAL_UNSUCCESSFUL",
    "LEADER_TIMEOUT_APPEAL_UNSUCCESSFUL",
}
ALL_APPEAL_TYPES = SUCCESSFUL_APPEAL_TYPES | UNSUCCESSFUL_APPEAL_TYPES

# scripts/07_generate_consensus_vectors.py emits this fixed time-unit model.
VECTOR_LEADER_TIMEOUT = 100
VECTOR_VALIDATOR_TIMEOUT = 200


class ConsensusConformanceViolation(AssertionError):
    """A vector difference is not explained by the approved fee changes."""


@dataclass(frozen=True)
class CaseDelta:
    source: str
    pattern: str
    example_index: int
    appellant_payout_delta: int
    vindicated_count: int
    vindication_payout: int
    upfront_reserve_delta: int
    sender_refund_delta: int

    @property
    def expected_red(self) -> bool:
        return any(
            (
                self.appellant_payout_delta,
                self.vindication_payout,
                self.upfront_reserve_delta,
                self.sender_refund_delta,
            )
        )


@dataclass(frozen=True)
class ConformanceReport:
    compared_cases: int
    exact_parity_cases: int
    expected_red_cases: int
    appellant_gap_cases: int
    vindication_gap_cases: int
    vindicated_validators: int
    appellant_payout_delta: int
    vindication_payout: int
    upfront_reserve_delta: int
    sender_refund_delta: int
    unclassified_deltas: int
    cases: tuple[CaseDelta, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = "EXPECTED_RED" if self.expected_red_cases else "PARITY"
        return result


def _fail(source: str, pattern: str, message: str) -> None:
    raise ConsensusConformanceViolation(f"{source} :: {pattern}: {message}")


def _round_signature(round_: dict[str, Any]) -> tuple[Any, ...]:
    votes = Counter(
        (validator["vote"], bool(validator.get("is_leader")))
        for validator in round_.get("validators", [])
    )
    return (
        int(round_.get("round_index", 0)),
        round_["type"],
        tuple(sorted(votes.items())),
    )


def _entry_buckets(entries: Iterable[dict[str, Any]]) -> Counter[tuple[Any, ...]]:
    return Counter(
        (
            int(entry["round_index"]),
            entry.get("role", "VALIDATOR"),
            int(entry["amount"]),
            "APPELLANT" if entry["address"].startswith("appealant") else "PARTICIPANT",
        )
        for entry in entries
    )


def _vote(vote: str) -> str:
    if vote == "LEADER_RECEIPT":
        return "AGREE"
    if vote == "LEADER_TIMEOUT":
        return "TIMEOUT"
    return vote


def _majority(validators: list[dict[str, Any]]) -> str:
    counts = Counter(_vote(validator["vote"]) for validator in validators)
    threshold = len(validators) // 2 + 1
    for vote in ("AGREE", "DISAGREE", "TIMEOUT"):
        if counts[vote] >= threshold:
            return vote
    return "UNDETERMINED"


def _previous_original_round(
    rounds: list[dict[str, Any]], appeal_round_index: int
) -> dict[str, Any] | None:
    for round_ in reversed(rounds[:appeal_round_index]):
        # Mirrors find_previous_normal_round: every non-appeal settlement
        # label is an eligible original round, including timeout-derived
        # labels such as LEADER_TIMEOUT_150%_NORMAL.
        if "APPEAL" not in round_["type"]:
            return round_
    return None


def _reward_counter_for_round(
    rewards: list[dict[str, Any]], round_index: int
) -> Counter[tuple[str, int]]:
    return Counter(
        (entry["address"], int(entry["amount"]))
        for entry in rewards
        if int(entry["round_index"]) == round_index and entry.get("role") == "VALIDATOR"
    )


def compare_case(
    legacy: dict[str, Any],
    future: dict[str, Any],
    *,
    source: str,
    pattern: str,
    example_index: int = 0,
) -> CaseDelta:
    """Compare one contract-conformant vector with one future-model vector."""

    legacy_rounds = legacy["initialState"]["rounds"]
    future_rounds = future["initialState"]["rounds"]
    if [_round_signature(r) for r in legacy_rounds] != [
        _round_signature(r) for r in future_rounds
    ]:
        _fail(source, pattern, "round types, sizes, or vote outcomes changed")

    legacy_state = legacy["expectedState"]
    future_state = future["expectedState"]
    if _entry_buckets(legacy_state["penalties"]) != _entry_buckets(
        future_state["penalties"]
    ):
        _fail(source, pattern, "penalty schedule changed")

    legacy_rewards = legacy_state["rewards"]
    future_rewards = future_state["rewards"]

    legacy_appellants = {
        int(entry["round_index"]): int(entry["amount"])
        for entry in legacy_rewards
        if entry.get("role") == "APPEALANT"
    }
    future_appellants = {
        int(entry["round_index"]): int(entry["amount"])
        for entry in future_rewards
        if entry.get("role") == "APPEALANT"
    }
    if legacy_appellants.keys() != future_appellants.keys():
        _fail(source, pattern, "successful-appellant custody rounds changed")

    appellant_delta = 0
    for round_index, legacy_amount in legacy_appellants.items():
        future_amount = future_appellants[round_index]
        if future_amount * 2 % 5:
            _fail(source, pattern, f"round {round_index} future return is not 2.5x")
        future_bond = future_amount * 2 // 5
        if legacy_amount != future_amount:
            if legacy_amount * 2 % 3:
                _fail(
                    source,
                    pattern,
                    f"round {round_index} legacy return is neither matching 2.5x "
                    "nor an integral 1.5x return",
                )
            legacy_bond = legacy_amount * 2 // 3
            if legacy_bond != future_bond:
                _fail(source, pattern, f"round {round_index} appeal bond changed")
        appellant_delta += future_amount - legacy_amount

    legacy_non_appellant = [
        entry for entry in legacy_rewards if entry.get("role") != "APPEALANT"
    ]
    future_non_appellant = [
        entry for entry in future_rewards if entry.get("role") != "APPEALANT"
    ]
    legacy_buckets = _entry_buckets(legacy_non_appellant)
    future_buckets = _entry_buckets(future_non_appellant)
    removed_buckets = legacy_buckets - future_buckets
    if removed_buckets:
        _fail(
            source, pattern, f"future model removes reward buckets: {removed_buckets}"
        )

    configured_vindication: Counter[tuple[Any, ...]] = Counter()
    for appeal_position, round_ in enumerate(future_rounds):
        if round_["type"] != "VALIDATOR_APPEAL_SUCCESSFUL":
            continue
        majority = _majority(round_.get("validators", []))
        if majority == "UNDETERMINED":
            continue
        original = _previous_original_round(future_rounds, appeal_position)
        if original is None:
            _fail(source, pattern, f"round {appeal_position} has no original round")

        expected_addresses = {
            validator["address"]
            for validator in original.get("validators", [])
            if _vote(validator["vote"]) == majority
        }
        future_round_rewards = _reward_counter_for_round(
            future_rewards, appeal_position
        )
        aligned_appeal_addresses = {
            validator["address"]
            for validator in round_.get("validators", [])
            if _vote(validator["vote"]) == majority
        }
        round_amounts = {amount for _, amount in future_round_rewards if amount > 0}
        if len(round_amounts) != 1:
            _fail(
                source,
                pattern,
                f"round {appeal_position} validator rewards are not uniform: "
                f"{sorted(round_amounts)}",
            )
        validator_reward = next(iter(round_amounts))
        appeal_committee_rewards = Counter(
            (address, validator_reward) for address in aligned_appeal_addresses
        )
        if appeal_committee_rewards - future_round_rewards:
            _fail(
                source,
                pattern,
                f"round {appeal_position} omits an aligned appeal voter",
            )
        added_round_rewards = future_round_rewards - appeal_committee_rewards
        if {address for address, _ in added_round_rewards} != expected_addresses:
            _fail(
                source,
                pattern,
                f"round {appeal_position} vindicates the wrong original voters: "
                f"expected {sorted(expected_addresses)}, got "
                f"{sorted(address for address, _ in added_round_rewards)}",
            )
        for (address, amount), count in added_round_rewards.items():
            if count != 1:
                _fail(
                    source,
                    pattern,
                    f"round {appeal_position} pays {address} vindication {count} times",
                )
            configured_vindication[
                (appeal_position, "VALIDATOR", amount, "PARTICIPANT")
            ] += 1

    actual_additions = future_buckets - legacy_buckets
    if actual_additions == configured_vindication:
        missing_vindication = actual_additions
    elif not actual_additions:
        missing_vindication = Counter()
    else:
        _fail(
            source,
            pattern,
            "unclassified reward delta: expected either exact parity or "
            f"{configured_vindication}, got {actual_additions}",
        )
    vindicated_count = sum(missing_vindication.values())
    vindication_payout = sum(
        amount * count for (_, _, amount, _), count in missing_vindication.items()
    )

    total_legacy_rewards = sum(int(entry["amount"]) for entry in legacy_rewards)
    total_future_rewards = sum(int(entry["amount"]) for entry in future_rewards)
    reward_delta = total_future_rewards - total_legacy_rewards
    if reward_delta != appellant_delta + vindication_payout:
        _fail(
            source,
            pattern,
            f"reward delta {reward_delta} is not appellant + vindication delta "
            f"{appellant_delta + vindication_payout}",
        )

    legacy_refund = int(legacy_state["sender_outcome"]["net_change"])
    future_refund = int(future_state["sender_outcome"]["net_change"])
    sender_refund_delta = future_refund - legacy_refund
    appeal_count = sum(round_["type"] in ALL_APPEAL_TYPES for round_ in future_rounds)
    configured_reserve_delta = sum(
        VECTOR_LEADER_TIMEOUT
        + NORMAL_ROUND_SIZES[min(appeal_ordinal + 1, len(NORMAL_ROUND_SIZES) - 1)]
        * VECTOR_VALIDATOR_TIMEOUT
        for appeal_ordinal in range(appeal_count)
    )
    legacy_pot = total_legacy_rewards + legacy_refund
    future_pot = total_future_rewards + future_refund
    upfront_reserve_delta = future_pot - legacy_pot
    if upfront_reserve_delta not in {0, configured_reserve_delta}:
        _fail(
            source,
            pattern,
            f"upfront reserve delta {upfront_reserve_delta} is neither parity nor "
            f"the configured 1.5x -> 2.5x delta {configured_reserve_delta}",
        )
    if sender_refund_delta != upfront_reserve_delta - reward_delta:
        _fail(
            source,
            pattern,
            f"sender refund delta {sender_refund_delta} violates the deposit "
            f"conservation identity; expected {upfront_reserve_delta - reward_delta}",
        )

    return CaseDelta(
        source=source,
        pattern=pattern,
        example_index=example_index,
        appellant_payout_delta=appellant_delta,
        vindicated_count=vindicated_count,
        vindication_payout=vindication_payout,
        upfront_reserve_delta=upfront_reserve_delta,
        sender_refund_delta=sender_refund_delta,
    )


def _load_pattern_files(directory: Path) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*_compressed.json")):
        if "rotations" in path.name:
            continue
        payload = json.loads(path.read_text())
        if payload.get("patterns"):
            files[path.name] = payload
    return files


def compare_vector_directories(legacy_dir: Path, future_dir: Path) -> ConformanceReport:
    """Compare every shared rotation-free compressed vector case."""

    legacy_files = _load_pattern_files(legacy_dir)
    future_files = _load_pattern_files(future_dir)
    if legacy_files.keys() != future_files.keys():
        missing_future = sorted(legacy_files.keys() - future_files.keys())
        missing_legacy = sorted(future_files.keys() - legacy_files.keys())
        raise ConsensusConformanceViolation(
            f"vector file set changed; missing future={missing_future}, "
            f"missing legacy={missing_legacy}"
        )

    case_deltas: list[CaseDelta] = []
    for file_name, legacy_file in legacy_files.items():
        future_file = future_files[file_name]
        legacy_patterns = legacy_file["patterns"]
        future_patterns = future_file["patterns"]
        if legacy_patterns.keys() != future_patterns.keys():
            missing_future = sorted(legacy_patterns.keys() - future_patterns.keys())
            missing_legacy = sorted(future_patterns.keys() - legacy_patterns.keys())
            raise ConsensusConformanceViolation(
                f"{file_name}: pattern set changed; missing future={missing_future[:5]}, "
                f"missing legacy={missing_legacy[:5]}"
            )
        for pattern, legacy_pattern in legacy_patterns.items():
            future_pattern = future_patterns[pattern]
            legacy_examples = legacy_pattern.get("examples", [])
            future_examples = future_pattern.get("examples", [])
            if len(legacy_examples) != len(future_examples):
                _fail(file_name, pattern, "example cardinality changed")
            for index, (legacy, future) in enumerate(
                zip(legacy_examples, future_examples, strict=True)
            ):
                case_deltas.append(
                    compare_case(
                        legacy,
                        future,
                        source=file_name,
                        pattern=pattern,
                        example_index=index,
                    )
                )

    exact = sum(not case.expected_red for case in case_deltas)
    expected_red = len(case_deltas) - exact
    return ConformanceReport(
        compared_cases=len(case_deltas),
        exact_parity_cases=exact,
        expected_red_cases=expected_red,
        appellant_gap_cases=sum(
            case.appellant_payout_delta > 0 for case in case_deltas
        ),
        vindication_gap_cases=sum(case.vindication_payout > 0 for case in case_deltas),
        vindicated_validators=sum(case.vindicated_count for case in case_deltas),
        appellant_payout_delta=sum(case.appellant_payout_delta for case in case_deltas),
        vindication_payout=sum(case.vindication_payout for case in case_deltas),
        upfront_reserve_delta=sum(case.upfront_reserve_delta for case in case_deltas),
        sender_refund_delta=sum(case.sender_refund_delta for case in case_deltas),
        unclassified_deltas=0,
        cases=tuple(case_deltas),
    )
