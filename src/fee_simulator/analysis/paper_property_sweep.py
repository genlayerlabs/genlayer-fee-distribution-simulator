"""Bounded exhaustive verification of the paper-facing payoff kernel."""

from dataclasses import asdict, dataclass
from typing import Dict, Iterator, List, Tuple

from src.fee_simulator.analysis.paper_payoff_kernel import (
    PaperPropertyViolation,
    certify_normal_round,
    certify_successful_validator_appeal,
)
from src.fee_simulator.core.majority import compute_majority
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.round_fee_distribution.appeal_validator_successful import (
    apply_appeal_validator_successful,
)
from src.fee_simulator.protocol.constants import (
    APPEAL_REWARD_MULTIPLE,
    APPEAL_ROUND_SIZES,
    NORMAL_ROUND_SIZES,
    PENALTY_REWARD_COEFFICIENT,
)
from src.fee_simulator.protocol.models import (
    Appeal,
    EventSequence,
    Rotation,
    Round,
    TransactionBudget,
    TransactionRoundResults,
)


@dataclass(frozen=True)
class VoteCounts:
    agree: int
    disagree: int
    timeout: int

    def __post_init__(self) -> None:
        if min(self.agree, self.disagree, self.timeout) < 0:
            raise ValueError("vote counts must be nonnegative")

    @property
    def size(self) -> int:
        return self.agree + self.disagree + self.timeout


@dataclass(frozen=True)
class PaperPropertySweepReport:
    normal_profiles_checked: int
    successful_appeal_profiles_checked: int
    end_to_end_appeal_profiles_checked: int
    live_label_ambiguities_detected: int
    clear_reversal_profiles_checked: int
    no_majority_appeal_profiles_checked: int
    maximum_vindicated_count_observed: int
    maximum_added_sender_cost_observed: int
    configured_rung_boundary_cases_checked: int
    largest_configured_vindication_count: int
    largest_configured_added_sender_cost: int
    validators_timeout: int
    penalty_per_minority_validator: int
    appeal_reward_multiple: float
    payoff_kernel: Dict[str, int]
    paper_margins: Dict[str, int]

    def as_dict(self) -> Dict:
        return asdict(self)


def enumerate_vote_counts(size: int) -> Iterator[VoteCounts]:
    for agree in range(size + 1):
        for disagree in range(size - agree + 1):
            yield VoteCounts(
                agree=agree,
                disagree=disagree,
                timeout=size - agree - disagree,
            )


def _address(index: int) -> str:
    return f"0x{index:040x}"


def _votes_from_counts(
    counts: VoteCounts, start_index: int, *, leader_receipt: bool
) -> Dict:
    vote_types = (
        ["AGREE"] * counts.agree
        + ["DISAGREE"] * counts.disagree
        + ["TIMEOUT"] * counts.timeout
    )
    votes = {}
    for offset, vote in enumerate(vote_types):
        address = _address(start_index + offset)
        votes[address] = (
            ["LEADER_RECEIPT", vote] if leader_receipt and offset == 0 else vote
        )
    return votes


def build_first_rung_case(
    original_counts: VoteCounts,
    appeal_counts: VoteCounts,
    *,
    leader_timeout: int = 100,
    validators_timeout: int = 200,
) -> Tuple[TransactionRoundResults, TransactionBudget, List[str]]:
    if original_counts.size != 5 or appeal_counts.size != 7:
        raise ValueError("first-rung cases require committee sizes 5 and 7")

    transaction_results = TransactionRoundResults(
        rounds=[
            Round(
                rotations=[
                    Rotation(
                        votes=_votes_from_counts(
                            original_counts, 1, leader_receipt=True
                        )
                    )
                ]
            ),
            Round(
                rotations=[
                    Rotation(
                        votes=_votes_from_counts(
                            appeal_counts, 101, leader_receipt=False
                        )
                    )
                ]
            ),
        ]
    )
    budget = TransactionBudget(
        leaderTimeout=leader_timeout,
        validatorsTimeout=validators_timeout,
        appealRounds=1,
        rotations=[0, 0],
        senderAddress=_address(1001),
        appeals=[Appeal(appealantAddress=_address(1002))],
        staking_distribution="constant",
    )
    return (
        transaction_results,
        budget,
        ["SKIP_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL"],
    )


def build_normal_case(
    counts: VoteCounts,
    *,
    leader_timeout: int = 100,
    validators_timeout: int = 200,
) -> Tuple[TransactionRoundResults, TransactionBudget, List[str]]:
    """Build a single ordinary round for end-to-end settlement."""

    transaction_results = TransactionRoundResults(
        rounds=[
            Round(
                rotations=[
                    Rotation(votes=_votes_from_counts(counts, 1, leader_receipt=True))
                ]
            )
        ]
    )
    budget = TransactionBudget(
        leaderTimeout=leader_timeout,
        validatorsTimeout=validators_timeout,
        appealRounds=0,
        rotations=[0],
        senderAddress=_address(1001),
        appeals=[],
        staking_distribution="constant",
    )
    addresses = list(transaction_results.rounds[0].rotations[-1].votes) + [
        budget.senderAddress
    ]
    return transaction_results, budget, addresses


def build_configured_rung_case(
    rung_index: int,
    original_counts: VoteCounts,
    appeal_counts: VoteCounts,
    *,
    leader_timeout: int = 100,
    validators_timeout: int = 200,
) -> Tuple[TransactionRoundResults, TransactionBudget, List[str], int]:
    """Build a synthetic history that places a case at one configured rung."""

    if rung_index < 0 or rung_index >= len(NORMAL_ROUND_SIZES):
        raise ValueError(f"invalid configured rung {rung_index}")
    if original_counts.size != NORMAL_ROUND_SIZES[rung_index]:
        raise ValueError("original count does not match configured normal size")
    if appeal_counts.size != APPEAL_ROUND_SIZES[rung_index]:
        raise ValueError("appeal count does not match configured appeal size")

    rounds = []
    round_labels = []
    appeals = []
    for prior_rung in range(rung_index):
        rounds.extend([Round(rotations=[]), Round(rotations=[])])
        round_labels.extend(["SKIP_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL"])
        appeals.append(Appeal(appealantAddress=_address(5000 + prior_rung)))

    round_index = len(rounds) + 1
    rounds.extend(
        [
            Round(
                rotations=[
                    Rotation(
                        votes=_votes_from_counts(
                            original_counts, 1, leader_receipt=True
                        )
                    )
                ]
            ),
            Round(
                rotations=[
                    Rotation(
                        votes=_votes_from_counts(
                            appeal_counts, 2001, leader_receipt=False
                        )
                    )
                ]
            ),
        ]
    )
    round_labels.extend(["SKIP_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL"])
    appeals.append(Appeal(appealantAddress=_address(6000 + rung_index)))

    budget = TransactionBudget(
        leaderTimeout=leader_timeout,
        validatorsTimeout=validators_timeout,
        appealRounds=rung_index + 1,
        rotations=[0] * (rung_index + 2),
        senderAddress=_address(7001),
        appeals=appeals,
        staking_distribution="constant",
    )
    return TransactionRoundResults(rounds=rounds), budget, round_labels, round_index


def verify_first_rung_paper_properties(
    *, leader_timeout: int = 100, validators_timeout: int = 200
) -> PaperPropertySweepReport:
    """Exhaust every vote-count equivalence class for sizes five and seven."""

    normal_profiles_checked = 0
    successful_appeal_profiles_checked = 0
    end_to_end_appeal_profiles_checked = 0
    live_label_ambiguities_detected = 0
    clear_reversal_profiles_checked = 0
    no_majority_appeal_profiles_checked = 0
    maximum_vindicated_count_observed = 0
    maximum_added_sender_cost_observed = 0
    configured_rung_boundary_cases_checked = 0
    largest_configured_vindication_count = 0
    largest_configured_added_sender_cost = 0

    normal_profiles = list(enumerate_vote_counts(5))
    appeal_profiles = list(enumerate_vote_counts(7))

    # Ordinary-round preservation payoffs for every 5-seat tally, through
    # the same transaction processor used by the simulator entry points.
    for normal_counts in normal_profiles:
        transaction_results, budget, addresses = build_normal_case(
            normal_counts,
            leader_timeout=leader_timeout,
            validators_timeout=validators_timeout,
        )
        events, round_labels = process_transaction(
            addresses, transaction_results, budget
        )
        if round_labels != ["NORMAL_ROUND"]:
            raise PaperPropertyViolation(
                "normal_round_shape",
                f"profile classified as {round_labels}",
            )
        certify_normal_round(transaction_results, 0, budget, events)
        normal_profiles_checked += 1

    # Every settlement-valid successful first-rung validator-appeal tally,
    # including NoMajority successes. Confirmation tallies are intentionally
    # excluded. Representable cases run through the full transaction
    # processor. The separate ambiguity counter exposes cases that the
    # simulator's receipt-shape heuristic cannot identify end to end.
    for original_counts in normal_profiles:
        original_votes = _votes_from_counts(original_counts, 1, leader_receipt=True)
        original_majority = compute_majority(original_votes)
        # Under the live classifier, validator appeals challenge Accepted
        # (MajorityAgree). MajorityDisagree is a leader-appeal path.
        if original_majority != "AGREE":
            continue

        for appeal_counts in appeal_profiles:
            appeal_votes = _votes_from_counts(appeal_counts, 101, leader_receipt=False)
            appeal_majority = compute_majority(appeal_votes)
            if appeal_majority == original_majority:
                continue

            transaction_results, budget, round_labels = build_first_rung_case(
                original_counts,
                appeal_counts,
                leader_timeout=leader_timeout,
                validators_timeout=validators_timeout,
            )
            classified_labels = label_rounds(transaction_results)
            if classified_labels[1] == "APPEAL_VALIDATOR_SUCCESSFUL":
                addresses = (
                    list(transaction_results.rounds[0].rotations[-1].votes)
                    + list(transaction_results.rounds[1].rotations[-1].votes)
                    + [
                        budget.senderAddress,
                        budget.appeals[0].appealantAddress,
                    ]
                )
                events, round_labels = process_transaction(
                    addresses, transaction_results, budget
                )
                if round_labels != classified_labels:
                    raise PaperPropertyViolation(
                        "appeal_shape",
                        "transaction processing changed the classified labels",
                    )
                end_to_end_appeal_profiles_checked += 1
            elif appeal_counts == VoteCounts(agree=0, disagree=0, timeout=7):
                # With no leader receipt and no cast Agree/Disagree ballot,
                # TransactionRoundResults does not encode enough information
                # for label_rounds to distinguish an all-timeout appeal from
                # a malformed normal round. Keep certifying the explicitly
                # labeled settlement path, but report the integration gap.
                live_label_ambiguities_detected += 1
            else:
                raise PaperPropertyViolation(
                    "appeal_overturn_rule",
                    f"profile classified as {classified_labels[1]}",
                )
            if classified_labels[1] != "APPEAL_VALIDATOR_SUCCESSFUL":
                events = apply_appeal_validator_successful(
                    transaction_results=transaction_results,
                    round_index=1,
                    budget=budget,
                    event_sequence=EventSequence(),
                    round_labels=round_labels,
                )
            certificate = certify_successful_validator_appeal(
                transaction_results,
                1,
                budget,
                round_labels,
                events,
            )
            successful_appeal_profiles_checked += 1
            if certificate.appeal_majority == "UNDETERMINED":
                no_majority_appeal_profiles_checked += 1
            else:
                clear_reversal_profiles_checked += 1
            maximum_vindicated_count_observed = max(
                maximum_vindicated_count_observed,
                certificate.vindicated_count,
            )
            maximum_added_sender_cost_observed = max(
                maximum_added_sender_cost_observed,
                certificate.added_sender_cost,
            )

    # Check the extremal vindication bound and NoMajority zero-correction
    # boundary at every configured normal/appeal committee-size rung. This is
    # not an exhaustive tally sweep above the first rung; it certifies the
    # economically maximal and zero-spread boundary profiles.
    for rung_index, (normal_size, appeal_size) in enumerate(
        zip(NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES)
    ):
        original_majority = (normal_size // 2) + 1
        original_counts = VoteCounts(
            agree=original_majority,
            disagree=normal_size - original_majority,
            timeout=0,
        )
        appeal_majority = (appeal_size // 2) + 1
        clear_reversal_counts = VoteCounts(
            agree=appeal_size - appeal_majority,
            disagree=appeal_majority,
            timeout=0,
        )
        no_majority_counts = VoteCounts(
            agree=appeal_size // 2,
            disagree=appeal_size // 2,
            timeout=appeal_size % 2,
        )

        for appeal_counts in (clear_reversal_counts, no_majority_counts):
            transaction_results, budget, round_labels, round_index = (
                build_configured_rung_case(
                    rung_index,
                    original_counts,
                    appeal_counts,
                    leader_timeout=leader_timeout,
                    validators_timeout=validators_timeout,
                )
            )
            events = apply_appeal_validator_successful(
                transaction_results=transaction_results,
                round_index=round_index,
                budget=budget,
                event_sequence=EventSequence(),
                round_labels=round_labels,
            )
            certificate = certify_successful_validator_appeal(
                transaction_results,
                round_index,
                budget,
                round_labels,
                events,
            )
            configured_rung_boundary_cases_checked += 1
            largest_configured_vindication_count = max(
                largest_configured_vindication_count,
                certificate.vindicated_count,
            )
            largest_configured_added_sender_cost = max(
                largest_configured_added_sender_cost,
                certificate.added_sender_cost,
            )

    penalty = PENALTY_REWARD_COEFFICIENT * validators_timeout
    return PaperPropertySweepReport(
        normal_profiles_checked=normal_profiles_checked,
        successful_appeal_profiles_checked=successful_appeal_profiles_checked,
        end_to_end_appeal_profiles_checked=(end_to_end_appeal_profiles_checked),
        live_label_ambiguities_detected=live_label_ambiguities_detected,
        clear_reversal_profiles_checked=clear_reversal_profiles_checked,
        no_majority_appeal_profiles_checked=no_majority_appeal_profiles_checked,
        maximum_vindicated_count_observed=maximum_vindicated_count_observed,
        maximum_added_sender_cost_observed=maximum_added_sender_cost_observed,
        configured_rung_boundary_cases_checked=(configured_rung_boundary_cases_checked),
        largest_configured_vindication_count=(largest_configured_vindication_count),
        largest_configured_added_sender_cost=(largest_configured_added_sender_cost),
        validators_timeout=validators_timeout,
        penalty_per_minority_validator=penalty,
        appeal_reward_multiple=APPEAL_REWARD_MULTIPLE,
        payoff_kernel={
            "normal_clear_aligned": validators_timeout,
            "normal_clear_minority": -penalty,
            "normal_no_majority": validators_timeout,
            "appeal_clear_aligned": validators_timeout,
            "appeal_clear_minority": -penalty,
            "appeal_no_majority": validators_timeout,
            "original_vindicated": validators_timeout,
            "original_other": 0,
            "original_no_majority": 0,
        },
        paper_margins={
            "clear_majority_preservation_spread": (validators_timeout + penalty),
            "no_majority_preservation_spread": 0,
            "clear_reversal_correction_spread": validators_timeout,
            "no_majority_correction_spread": 0,
        },
    )
