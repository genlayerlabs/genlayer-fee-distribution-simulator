# /show-graph — Display the Transaction Graph

Display the TRANSACTION_GRAPH showing all valid state transitions, node metadata, and available paths.

## Usage

- `/show-graph` — show full graph with transitions and metadata
- `/show-graph LEADER_RECEIPT_MAJORITY_AGREE` — show transitions from a specific node

## Instructions

1. Read the graph definition from `src/fee_simulator/specification/state_machine/graph.py`.

2. Display the graph in a readable format:

   **Full graph** (no arguments): Show every node with its outgoing transitions and metadata (rotation/idle support), formatted as a table or structured list. Group nodes into categories:
   - **Start**: START
   - **Normal Rounds**: LEADER_RECEIPT_MAJORITY_AGREE, LEADER_RECEIPT_MAJORITY_DISAGREE, LEADER_RECEIPT_UNDETERMINED, LEADER_RECEIPT_MAJORITY_TIMEOUT, LEADER_TIMEOUT
   - **Validator Appeals**: VALIDATOR_APPEAL_SUCCESSFUL, VALIDATOR_APPEAL_UNSUCCESSFUL
   - **Leader Appeals**: LEADER_APPEAL_SUCCESSFUL, LEADER_APPEAL_UNSUCCESSFUL
   - **Leader Timeout Appeals**: LEADER_APPEAL_TIMEOUT_SUCCESSFUL, LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL
   - **End**: END

   For each node, show:
   - Outgoing transitions (list of valid next nodes)
   - Metadata: `rotations` (bool), `idle` (bool)

   **Single node** (with `$ARGUMENTS`): Show only that node's transitions and metadata.

3. Also display the numeric shorthand mapping for use with `/simulate`:
   - 1=LEADER_RECEIPT_MAJORITY_AGREE, 2=LEADER_RECEIPT_MAJORITY_DISAGREE, etc.

4. Show path statistics: how many valid paths exist for lengths 3 through 7.

No conda activation or script execution needed — just read the file and format the output directly.
