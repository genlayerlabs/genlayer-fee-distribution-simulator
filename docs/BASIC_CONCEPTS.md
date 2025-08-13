# Basic Concepts of GenLayer Fee Distribution

This document explains the fundamental concepts behind the GenLayer consensus and fee distribution mechanism. Understanding these concepts is essential to comprehending the purpose and function of this simulator.

## Core Actors

The system involves several key roles:

-   **Sender**: The user who initiates a transaction and provides the budget to pay for its processing.
-   **Leader**: A validator chosen to lead a consensus round. The leader is responsible for proposing a result for the transaction.
-   **Validator**: A participant in a consensus round who votes on the leader's proposed result.
-   **Appellant**: A participant (either the leader or a validator) who disputes the outcome of a round by paying an **appeal bond** to initiate an appeal round.

## The Transaction Lifecycle

A "transaction" in this context is not a simple transfer but a multi-round process to achieve consensus on a result.

### 1. Normal Rounds

-   A **Leader** is selected for the round.
-   The Leader proposes a result and sends a `LEADER_RECEIPT`.
-   **Validators** vote on the leader's proposal.

### 2. Voting and Outcomes

Validators can cast one of several votes:

-   **`AGREE`**: The validator agrees with the leader's proposal.
-   **`DISAGREE`**: The validator disagrees with the leader's proposal.
-   **`TIMEOUT`**: The validator failed to submit a vote in time.
-   **`IDLE`**: The validator was non-responsive and did not participate. They are removed from the round and replaced by a reserve if available.

The collective votes determine the round's outcome:

-   **Majority**: If >50% of participants vote the same way (e.g., `AGREE`), that becomes the majority outcome.
-   **Minority**: Participants who did not vote with the majority.
-   **Undetermined**: If no single vote type achieves a majority, the outcome is undetermined.
-   **`LEADER_TIMEOUT`**: If the leader fails to submit a `LEADER_RECEIPT`, the round ends in a timeout.

## The Appeal Process

If a participant believes the outcome of a round was incorrect, they can initiate an appeal.

-   **Purpose**: To challenge the result of a normal round. This is the core dispute resolution mechanism.
-   **Initiation**: An **Appellant** pays an **Appeal Bond** to start a new, larger appeal round.
-   **Fresh Participants**: Appeal rounds are conducted by a new, larger set of validators who did not participate in the original round, ensuring impartiality.
-   **Outcomes**:
    -   **Successful Appeal**: If the appeal round's outcome overturns the original round's outcome. The original round is retroactively marked as `SKIP_ROUND`.
    -   **Unsuccessful Appeal**: If the appeal round's outcome confirms the original round's outcome.

## Economics: Fees, Rewards, and Penalties

The system is designed to economically incentivize honest and timely participation.

#### Fees & Rewards

-   **`leaderTimeout` & `validatorsTimeout`**: These are the basic fee units paid from the Sender's budget.
-   **Normal Round (Majority Outcome)**:
    -   The **Leader** earns `leaderTimeout` + `validatorsTimeout`.
    -   **Majority Validators** each earn `validatorsTimeout`.
-   **Successful Appeal**:
    -   The **Appellant** is rewarded handsomely, receiving **1.5x their appeal bond** back (a 50% return on investment).

#### Penalties

-   **`burns`**:
    -   **Minority Validators** in a normal round with a clear majority have a portion of their fees `burned` as a penalty for being incorrect. The penalty is `PENALTY_REWARD_COEFFICIENT * validatorsTimeout`.
    -   An **unsuccessful Appellant** loses their entire appeal bond, which is either burned or distributed to the participants of the next round.
-   **`slashing`**:
    -   A more severe penalty applied directly to a validator's staked capital.
    -   **`IDLE`** validators are slashed a percentage of their stake (`IDLE_PENALTY_COEFFICIENT`).
    -   Validators committing **Deterministic Violations** (e.g., cryptographic failures) are slashed a larger percentage (`DETERMINISTIC_VIOLATION_PENALTY_COEFFICIENT`).

## Round Sizes and Security Escalation

The system is designed to increase security in response to contention.

-   **`NORMAL_ROUND_SIZES`**: `[5, 11, 23, ...]`
-   **`APPEAL_ROUND_SIZES`**: `[7, 13, 25, ...]`

1.  **Escalation**: Each appeal round uses more validators than the last, making it progressively harder and more expensive to challenge the consensus.
2.  **Cumulative Participation**: Normal rounds reuse the cumulative set of all validators who have participated in any previous round (normal or appeal). This ensures that after a dispute (which introduces many new validators), the next normal round has a much higher security level.
3.  **Mechanical Brake**: If an appeal follows another *unsuccessful* appeal, its size is reduced by 2. This is a "mechanical brake" to prevent runaway security escalation from long chains of failed appeals.

For a detailed explanation of the algorithm, see [ADDRESS_ALLOCATION_ALGORITHM.md](./ADDRESS_ALLOCATION_ALGORITHM.md).

## Putting It All Together: A Simple Path

Consider the path: `Normal (Majority Agrees) → Validator Appeal (Successful) → Normal`

1.  **Round 0 (`NORMAL_ROUND`)**: A leader and 5 validators participate. A majority agrees, but a minority disagrees and decides to appeal.
2.  **Round 1 (`APPEAL_VALIDATOR_SUCCESSFUL`)**: An appellant from the minority pays an appeal bond. A new set of 7 validators is brought in. They vote, and this time the outcome is `DISAGREE`, overturning the original result.
    -   The appellant receives 1.5x their bond back.
    -   The original majority from Round 0 is penalized.
3.  **Round 2 (`NORMAL_ROUND`)**: Because of the successful appeal, the original Round 0 is now considered invalid. Its label is retroactively changed to `SKIP_ROUND`. The system proceeds to a new normal round.
    -   This new normal round will be much larger (11 participants), reusing the validators from both Round 0 and Round 1 to ensure a higher level of security after the dispute.

