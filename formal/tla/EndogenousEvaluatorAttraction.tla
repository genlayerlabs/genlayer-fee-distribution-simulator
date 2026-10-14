---- MODULE EndogenousEvaluatorAttraction ----
EXTENDS Integers, PaperFeeKernel

\* This is the composition layer above the executable fee model. TLA+ does
\* not manufacture probabilities: MinPreservationTasks and MinCorrectionTasks
\* are deterministic lower bounds on settlement-effective opportunities in
\* each finite epoch. CostSavingPerTask and CapabilityCostPerEpoch are the
\* paper's measured external inputs. The four settlement spreads are required
\* to equal the generated PaperFeeKernel values in the green configuration.

CONSTANTS
    Population,
    BootstrapThreshold,
    InitialCompetent,
    EpochLength,
    MaxEpochs,
    MinPreservationTasks,
    MinCorrectionTasks,
    CostSavingPerTask,
    CapabilityCostPerEpoch,
    TurnoverBound,
    StrictPayoffResponse,
    PreservationSpread,
    CorrectionSpread,
    NoMajorityPreservation,
    NoMajorityCorrection

VARIABLES
    competent,
    slot,
    epoch,
    preservationTasks,
    correctionTasks,
    zeroSpreadTasks,
    epochAdvantage

vars == <<
    competent,
    slot,
    epoch,
    preservationTasks,
    correctionTasks,
    zeroSpreadTasks,
    epochAdvantage
>>

Min(a, b) == IF a <= b THEN a ELSE b
Max(a, b) == IF a >= b THEN a ELSE b

ASSUME
    /\ Population \in Nat \ {0}
    /\ BootstrapThreshold \in 1..Population
    /\ InitialCompetent \in 0..Population
    /\ EpochLength \in Nat \ {0}
    /\ MaxEpochs \in Nat
    /\ MaxEpochs >= Population - InitialCompetent
    /\ MinPreservationTasks \in 0..EpochLength
    /\ MinCorrectionTasks \in 0..EpochLength
    /\ MinPreservationTasks + MinCorrectionTasks <= EpochLength
    /\ CostSavingPerTask \in Nat
    /\ CapabilityCostPerEpoch \in Nat
    /\ TurnoverBound \in 1..Population
    /\ StrictPayoffResponse \in BOOLEAN
    /\ PreservationSpread \in Nat
    /\ CorrectionSpread \in Nat
    /\ NoMajorityPreservation \in Int
    /\ NoMajorityCorrection \in Int

TaskKinds == {
    "preservation",
    "correction",
    "noMajorityPreservation",
    "noMajorityCorrection"
}

GoodBasin == competent >= BootstrapThreshold

TaskSpread(kind) ==
    CASE kind = "preservation" ->
            IF GoodBasin THEN PreservationSpread ELSE -PreservationSpread
      [] kind = "correction" -> CorrectionSpread
      [] kind = "noMajorityPreservation" -> NoMajorityPreservation
      [] OTHER -> NoMajorityCorrection

Init ==
    /\ competent = InitialCompetent
    /\ slot = 0
    /\ epoch = 0
    /\ preservationTasks = 0
    /\ correctionTasks = 0
    /\ zeroSpreadTasks = 0
    /\ epochAdvantage = 0

DoTask(kind) ==
    /\ epoch < MaxEpochs
    /\ slot < EpochLength
    /\ kind \in TaskKinds
    /\ LET nextPreservation ==
               preservationTasks + IF kind = "preservation" THEN 1 ELSE 0
           nextCorrection ==
               correctionTasks + IF kind = "correction" THEN 1 ELSE 0
           nextZero ==
               zeroSpreadTasks +
                   IF kind \in {
                       "noMajorityPreservation",
                       "noMajorityCorrection"
                   }
                   THEN 1
                   ELSE 0
           nextSlot == slot + 1
           preservationDeficit ==
               Max(0, MinPreservationTasks - nextPreservation)
           correctionDeficit ==
               Max(0, MinCorrectionTasks - nextCorrection)
           remainingSlots == EpochLength - nextSlot
       IN
       /\ preservationDeficit + correctionDeficit <= remainingSlots
       /\ preservationTasks' = nextPreservation
       /\ correctionTasks' = nextCorrection
       /\ zeroSpreadTasks' = nextZero
       /\ slot' = nextSlot
       /\ epochAdvantage' =
              epochAdvantage + TaskSpread(kind) - CostSavingPerTask
    /\ UNCHANGED <<competent, epoch>>

SomeTask == \E kind \in TaskKinds: DoTask(kind)

EpochNet == epochAdvantage - CapabilityCostPerEpoch

PositivePopulationStep ==
    IF competent = Population
    THEN competent' = Population
    ELSE IF StrictPayoffResponse
         THEN competent' \in
                  (competent + 1)..Min(
                      Population,
                      competent + TurnoverBound
                  )
         ELSE competent' \in
                  competent..Min(Population, competent + TurnoverBound)

NegativePopulationStep ==
    IF competent = 0
    THEN competent' = 0
    ELSE IF StrictPayoffResponse
         THEN competent' \in
                  Max(0, competent - TurnoverBound)..(competent - 1)
         ELSE competent' \in
                  Max(0, competent - TurnoverBound)..competent

AdvanceEpoch ==
    /\ epoch < MaxEpochs
    /\ slot = EpochLength
    /\ IF EpochNet > 0
          THEN PositivePopulationStep
          ELSE IF EpochNet < 0
               THEN NegativePopulationStep
               ELSE competent' = competent
    /\ slot' = 0
    /\ epoch' = epoch + 1
    /\ preservationTasks' = 0
    /\ correctionTasks' = 0
    /\ zeroSpreadTasks' = 0
    /\ epochAdvantage' = 0

Next == SomeTask \/ AdvanceEpoch

Spec ==
    /\ Init
    /\ [][Next]_vars
    /\ WF_vars(SomeTask)
    /\ WF_vars(AdvanceEpoch)

TypeOK ==
    /\ competent \in 0..Population
    /\ slot \in 0..EpochLength
    /\ epoch \in 0..MaxEpochs
    /\ preservationTasks \in 0..slot
    /\ correctionTasks \in 0..slot
    /\ zeroSpreadTasks \in 0..slot
    /\ preservationTasks + correctionTasks + zeroSpreadTasks = slot
    /\ epochAdvantage \in Int

FeeKernelLinked ==
    /\ FeeKernelWellFormed
    /\ PreservationSpread = ClearMajorityPreservationSpread
    /\ CorrectionSpread = ClearReversalCorrectionSpread
    /\ NoMajorityPreservation = NoMajorityPreservationSpread
    /\ NoMajorityCorrection = NoMajorityCorrectionSpread

GuaranteedEpochMargin ==
      MinPreservationTasks * PreservationSpread
    + MinCorrectionTasks * CorrectionSpread
    - EpochLength * CostSavingPerTask
    - CapabilityCostPerEpoch

CorrectionReserveMargin ==
      MinCorrectionTasks * CorrectionSpread
    - EpochLength * CostSavingPerTask
    - CapabilityCostPerEpoch

RewardCorridor == GuaranteedEpochMargin > 0
CorrectionReserveFunded == CorrectionReserveMargin > 0

BoundaryMarginRealized ==
    (GoodBasin /\ slot = EpochLength) =>
        EpochNet >= GuaranteedEpochMargin

CompetenceNeverFalls == competent >= InitialCompetent
FullCompetence == competent = Population
ConvergedByHorizon == epoch = MaxEpochs => FullCompetence
EventuallyStableFullCompetence == <>[](FullCompetence)

====
