# /simulate — Simulate a Transaction Path

Simulate a specific transaction path through the fee distribution system and display all results.

## Usage

- `/simulate LEADER_RECEIPT_MAJORITY_AGREE` — single normal round
- `/simulate LEADER_RECEIPT_MAJORITY_AGREE VALIDATOR_APPEAL_SUCCESSFUL LEADER_RECEIPT_MAJORITY_DISAGREE` — multi-round
- `/simulate 1,8,2` — using numeric shorthand

## Numeric Shorthand

Map numbers to graph nodes:
- 1 = LEADER_RECEIPT_MAJORITY_AGREE
- 2 = LEADER_RECEIPT_MAJORITY_DISAGREE
- 3 = LEADER_RECEIPT_UNDETERMINED
- 4 = LEADER_RECEIPT_MAJORITY_TIMEOUT
- 5 = LEADER_TIMEOUT
- 6 = LEADER_APPEAL_SUCCESSFUL
- 7 = LEADER_APPEAL_UNSUCCESSFUL
- 8 = VALIDATOR_APPEAL_SUCCESSFUL
- 9 = VALIDATOR_APPEAL_UNSUCCESSFUL
- 10 = LEADER_APPEAL_TIMEOUT_SUCCESSFUL
- 11 = LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL

## Instructions

Write and execute a Python script that:

1. **Parses the path** from `$ARGUMENTS`. If the input is comma-separated numbers, map them using the shorthand above. Wrap the node list with `"START"` at the beginning and `"END"` at the end.

2. **Runs the simulation** using this code pattern:

```python
import sys
sys.path.insert(0, ".")
from src.fee_simulator.utils import generate_random_eth_address
from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.core.round_fee_distribution import process_transaction
from src.fee_simulator.specification.invariants.checker import check_all_invariants
from src.fee_simulator.display.utils import display_summary_table, display_fee_events_table

addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[999]
appealant_address = addresses[998]

path = ["START", ...nodes..., "END"]  # from user input

transaction_results, budget = path_to_transaction_results(
    path, addresses, sender_address, appealant_address,
    leader_timeout=100, validators_timeout=200
)
labels = label_rounds(transaction_results)
fee_events, slashing_events = process_transaction(addresses, transaction_results, budget)

# Display results
print(f"\nPath: {' -> '.join(path)}")
print(f"Round labels: {labels}")
display_fee_events_table(fee_events, transaction_results, budget, labels)
display_summary_table(fee_events, transaction_results, budget, labels)

# Check invariants
results = check_all_invariants(fee_events, budget, transaction_results, labels)
all_pass = all(r for r in results.values())
print(f"\nInvariants: {'ALL PASSED' if all_pass else 'FAILURES DETECTED'}")
if not all_pass:
    for name, passed in results.items():
        if not passed:
            print(f"  FAILED: {name}")
```

3. Run the script with conda activation:
```bash
source /home/jmlago/miniconda3/bin/activate && conda activate kpi-tracker && python /tmp/simulate_path.py
```

4. Show the output to the user. If any invariant fails, highlight it.

## Valid Transitions

Not all node sequences are valid. If a path fails validation, suggest valid next nodes based on the TRANSACTION_GRAPH. The graph is defined in `src/fee_simulator/specification/state_machine/graph.py`.
