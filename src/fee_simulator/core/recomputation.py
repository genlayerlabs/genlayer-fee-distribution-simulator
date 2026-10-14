"""Funded normal-round generations after an upstream state change (CF-008).

This supplements the single-transaction round engine. Upstream appeals are
represented by monotonic ancestor revisions, not by appending an appeal to
the descendant's own rounds. The descendant pays one deposit for its lifetime.
Its own appeal rounds and receipt/storage execution charges are outside this
normal-round model; callers must not silently pass either as time-unit work.
"""

from collections import defaultdict
from copy import deepcopy

from src.fee_simulator.core.majority import compute_majority
from src.fee_simulator.core.round_fee_distribution.distribute_round import distribute_round
from src.fee_simulator.protocol.models import (
    EventSequence,
    FeeEvent,
    Round,
    TransactionBudget,
    TransactionRoundResults,
)


class RecomputationLedger:
    def __init__(self, budget: TransactionBudget, ancestors: list[str], committee_size: int = 5):
        if budget.appealRounds != 0 or len(budget.rotations) != 1:
            raise ValueError("This model accepts one normal-round budget, without descendant appeals")
        if committee_size < 1 or budget.rotations[0] < 0:
            raise ValueError("Invalid funded attempt shape")
        self.budget = budget.model_copy(deep=True)
        self.committee_size = committee_size
        self.rotations_left = budget.rotations[0]
        self.deposited = (self.rotations_left + 1) * (
            budget.leaderTimeout + committee_size * budget.validatorsTimeout
        )
        self.ancestor_revisions = dict.fromkeys(ancestors, 0)
        self.state = "Proposing"
        self.generation = 0
        self.history = []
        self._events = []
        self._sequence = EventSequence()

    def complete_generation(self, round_result: Round):
        if self.state != "Proposing":
            raise ValueError("Generation is not open")
        if not round_result.rotations:
            raise ValueError("A completed generation must contain work")
        if any(len(attempt.votes) != self.committee_size for attempt in round_result.rotations):
            raise ValueError("Committee differs from the funded shape")
        rotations = len(round_result.rotations) - 1
        if rotations > self.rotations_left:
            raise ValueError("Rotation budget exhausted")
        if compute_majority(round_result.rotations[-1].votes) != "AGREE":
            raise ValueError("This model requires an Accepted final attempt")
        results = TransactionRoundResults(rounds=[round_result.model_copy(deep=True)])
        events = distribute_round(results, 0, "NORMAL_ROUND", self.budget, self._sequence, ["NORMAL_ROUND"])
        self.rotations_left -= rotations
        self._events.extend(events)
        self.history.append({
            "generation": self.generation,
            "ancestry": deepcopy(self.ancestor_revisions),
            "round": results.rounds[0].model_dump(),
            "earned": sum(event.earned for event in events),
            "invalidated": False,
        })
        self.state = "Accepted"
        self._assert_backing()

    def record_partial_generation(self, leader: str, revealed_validators: list[str]):
        """Record completed duties before a capture is invalidated.

        A proposal earns one leader allocation. Each recorded validator reveal
        earns one validator allocation; a commit alone has not completed that
        duty. Upstream invalidation provides no verdict against these voters.
        """
        if self.state != "Proposing":
            raise ValueError("Generation is not open")
        if len(set(revealed_validators)) != len(revealed_validators) or len(revealed_validators) > self.committee_size:
            raise ValueError("Invalid reveal membership")
        events = [FeeEvent(sequence_id=self._sequence.next_id(), address=leader,
                           role="LEADER", earned=self.budget.leaderTimeout)]
        events.extend(FeeEvent(sequence_id=self._sequence.next_id(), address=address,
                               role="VALIDATOR", earned=self.budget.validatorsTimeout)
                      for address in revealed_validators)
        self._events.extend(events)
        self.history.append({"generation": self.generation,
                             "ancestry": deepcopy(self.ancestor_revisions),
                             "partial": {"leader": leader, "reveals": list(revealed_validators)},
                             "earned": sum(event.earned for event in events), "invalidated": False})
        self.state = "Executing"
        self._assert_backing()

    def invalidate(self, ancestor: str, revision: int):
        if ancestor not in self.ancestor_revisions:
            raise ValueError("No dependency on this ancestor")
        if revision <= self.ancestor_revisions[ancestor]:
            return
        if self.state == "Finalized":
            raise ValueError("Finalization is irreversible")
        if self.state not in ("Accepted", "Executing", "Invalidated", "Canceled"):
            raise ValueError("No captured work to invalidate")
        self.ancestor_revisions[ancestor] = revision
        if self.state in ("Invalidated", "Canceled"):
            return
        self.history[-1]["invalidated"] = True
        self.state = "Invalidated" if self.rotations_left else "Canceled"

    def resume(self):
        if self.state == "Proposing":
            return  # a repeated continuation cannot charge twice
        if self.state != "Invalidated" or not self.rotations_left:
            raise ValueError("No funded recomputation available")
        self.rotations_left -= 1
        self.generation += 1
        self.state = "Proposing"

    def finalize(self):
        if self.state == "Finalized":
            return
        if self.state != "Accepted":
            raise ValueError("Invalid state cannot finalize")
        self.state = "Finalized"

    @property
    def entitlements(self):
        amounts = defaultdict(int)
        for event in self._events:
            amounts[event.address] += event.earned
        return dict(amounts)

    @property
    def consumed(self):
        return sum(self.entitlements.values())

    @property
    def refund(self):
        if self.state not in ("Canceled", "Finalized"):
            raise ValueError("Unfinished work still owns its backing")
        return self.deposited - self.consumed

    def _assert_backing(self):
        if self.consumed > self.deposited:
            raise ValueError("Compensation exceeds the single funded deposit")
