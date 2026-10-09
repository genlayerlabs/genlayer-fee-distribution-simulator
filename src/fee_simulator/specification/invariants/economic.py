"""Owner-level checks over supplied, matched defensive policy fixtures.

These checks do not infer misconduct from disagreement, or generate transaction
paths. The fixture author must justify why the comparison is a deviation from
an honest baseline with the same work, external outcomes and budget assumptions.
Only the time-unit fee ledger is modeled; this is not a token-profit certificate.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Mapping, Sequence

from src.fee_simulator.protocol.models import FeeEvent
from .definitions.common import InvariantViolation


FEE_COMPONENTS = frozenset({"time_unit_fees"})
FEE_ROLES = frozenset({"SENDER", "LEADER", "VALIDATOR", "APPEALANT", "TOPPER"})


@dataclass(frozen=True)
class EconomicComparison:
    """Explicit assumptions needed in addition to a single settlement trace.

    ``owners`` groups addresses under economic control, including aliases in
    either trace. ``coalition`` is the set of deviating owners. Honest appeal
    rewards must not be classified as deviations merely because they profit.
    Protected owners have an independently chosen maximum incremental loss;
    zero means no extra liability relative to the supplied honest baseline.
    """

    baseline_events: Sequence[FeeEvent]
    owners: Mapping[str, str]
    coalition: frozenset[str]
    rationale: str
    protected_loss_limits: Mapping[str, int] = field(default_factory=dict)
    required_components: frozenset[str] = FEE_COMPONENTS
    required_roles: frozenset[str] = frozenset()


def owner_net_payoffs(
    events: Sequence[FeeEvent], owners: Mapping[str, str]
) -> dict[str, int]:
    """Count every fee leg exactly once, without filtering votes or round labels.

    Appellant ``cost`` debits a bond; appellant ``burned`` records disposal of
    that already-debited bond. Validator/leader burns and slashes are additional
    liabilities. ``staked`` is an opening balance, not income or a new debit.
    Reimbursements, developer royalties and actual execution costs are absent.

    A failed bond may be disposed of in a successor round. Validate aggregate
    debit coverage per appellant across the complete transaction, not equality
    of posting and disposal round indices. This is not per-obligation provenance
    assurance; that requires a stable bond identifier absent from FeeEvent.
    """
    net = defaultdict(int)
    bonds = defaultdict(int)
    bond_burns = defaultdict(int)
    for event in events:
        owner = owners.get(event.address)
        if not owner:
            raise InvariantViolation(
                "economic_coverage", f"Missing owner for address {event.address}"
            )
        monetary = event.earned or event.cost or event.burned or event.slashed
        if monetary and event.role not in FEE_ROLES:
            raise InvariantViolation(
                "economic_coverage", "Monetary event has no supported fee role"
            )
        penalty = event.burned
        if event.role == "APPEALANT":
            key = event.address
            bonds[key] += event.cost
            bond_burns[key] += event.burned
            penalty = 0
        net[owner] += event.earned - event.cost - penalty - event.slashed

    for key, burned in bond_burns.items():
        if burned > bonds[key]:
            raise InvariantViolation(
                "economic_coverage",
                f"Appellant burn {burned} exceeds recorded bond debit {bonds[key]}",
            )
    return dict(net)


def check_economic_invariants(
    fee_events: Sequence[FeeEvent], comparison: EconomicComparison
) -> tuple[bool, list[str]]:
    """Reject a profitable specified deviation or excessive honest liability.

    Missing ownership or unsupported required accounting components fail the
    check. A pass is conditional on the supplied baseline and declared scope;
    fee balances alone cannot establish causation or who funded a payout.
    """
    violations = []
    unsupported = comparison.required_components - FEE_COMPONENTS
    unsupported_roles = comparison.required_roles - FEE_ROLES
    if unsupported or unsupported_roles:
        return False, [
            "economic_coverage: Unmodeled required components/roles: "
            + ", ".join(sorted(unsupported | unsupported_roles))
        ]
    known_owners = set(comparison.owners.values())
    if not comparison.rationale.strip() or not comparison.coalition:
        return False, ["economic_coverage: A coalition and baseline rationale are required"]
    if not comparison.coalition <= known_owners:
        return False, ["economic_coverage: Coalition contains an unmapped owner"]
    if not set(comparison.protected_loss_limits) <= known_owners:
        return False, ["economic_coverage: Protected owner is unmapped"]
    if comparison.coalition & comparison.protected_loss_limits.keys():
        return False, ["economic_coverage: Coalition and protected owners overlap"]
    if any(type(limit) is not int or limit < 0 for limit in comparison.protected_loss_limits.values()):
        return False, ["economic_coverage: Loss limits must be nonnegative integer time units"]
    try:
        baseline = owner_net_payoffs(comparison.baseline_events, comparison.owners)
        observed = owner_net_payoffs(fee_events, comparison.owners)
    except InvariantViolation as exc:
        return False, [f"{exc.invariant_name}: {exc.message}"]
    present_owners = set(baseline) | set(observed)
    required_owners = comparison.coalition | comparison.protected_loss_limits.keys()
    if not required_owners <= present_owners:
        return False, ["economic_coverage: An evaluated owner has no events in either trace"]

    delta = {
        owner: observed.get(owner, 0) - baseline.get(owner, 0)
        for owner in present_owners
    }
    gain = sum(delta[owner] for owner in comparison.coalition)
    if gain > 0:
        violations.append(
            f"no_profitable_deviation: Coalition gains {gain} time units over baseline"
        )
    for owner, limit in comparison.protected_loss_limits.items():
        if delta[owner] < -limit:
            violations.append(
                f"honest_liability: Owner {owner} loses {-delta[owner]} extra time units; "
                f"limit is {limit}"
            )
    return not violations, violations


def appeal_expected_payoff(
    *, bond: int, gross_success_return: int, success_probability: Fraction,
    private_cost: int = 0,
) -> Fraction:
    """Paper payoff q*R - (1-q)*B - c, with R = gross return - B.

    This assumes zero outside benefit and full bond loss on failure. Supply the
    actual integer success payout to retain settlement rounding at small bonds.
    """
    if any(type(value) is not int or value < 0 for value in (bond, gross_success_return, private_cost)):
        raise ValueError("Bond, gross return and cost must be nonnegative integers")
    if bond == 0:
        raise ValueError("Bond must be positive")
    if not isinstance(success_probability, Fraction) or not 0 <= success_probability <= 1:
        raise ValueError("Success probability must be an exact Fraction in [0, 1]")
    return success_probability * gross_success_return - bond - private_cost


def check_appeal_participation(**terms) -> None:
    """Require strict positive private incentive, not zero-cost indifference."""
    payoff = appeal_expected_payoff(**terms)
    if payoff <= 0:
        raise InvariantViolation(
            "appeal_participation", f"Expected appeal payoff must be positive; got {payoff}"
        )
