# GenLayer Fee Distribution Simulator

## Overview

The GenLayer Fee Distribution Simulator is a comprehensive Python-based system for modeling and testing fee distribution mechanisms in the GenLayer blockchain validator network. It uses a path-based approach to exhaustively test all possible transaction scenarios, ensuring correctness through rigorous invariant checking.

The simulator follows a deterministic flow: **TRANSITIONS_GRAPH → Path → TransactionRoundResults → Round Labels → Fee Distribution**, where each step is purely functional and content-based rather than index-based.

## Key Features

- **Path-Based Testing**: Generates all valid transaction paths from TRANSITIONS_GRAPH for exhaustive testing
- **Content-Based Round Detection**: Identifies round types by analyzing vote patterns, not indices
- **22 Invariants**: Comprehensive invariant checking ensures correctness (conservation of value, non-negative balances, etc.)
- **Role-Based Fee Distribution**: Allocates fees based on participant roles (Leader, Validator, Sender, Appealant)
- **Appeal Mechanisms**: Handles leader and validator appeals with proper bond calculations
- **Special Pattern Recognition**: Automatically transforms round labels based on transaction patterns
- **Visualization Tools**: Rich formatted tables for transaction results and fee distributions
- **Path JSON Export**: Generate compressed JSON files for all paths for external verification
- **Modular Architecture**: Clean separation between path generation, transaction processing, and fee distribution

## Project Structure

```
src/
└── fee_simulator/
    ├── core/                     # Core logic
    │   ├── round_fee_distribution/  # Fee distribution strategies
    │   │   ├── normal_round.py
    │   │   ├── appeal_*_successful.py
    │   │   ├── appeal_*_unsuccessful.py
    │   │   ├── leader_timeout_*.py
    │   │   └── split_previous_appeal_bond.py
    │   ├── path_to_transaction.py   # Path → Transaction converter
    │   ├── round_labeling.py        # Content-based round type detection
    │   ├── transaction_processing.py # Main processing pipeline
    │   ├── bond_computing.py        # Appeal bond calculations
    │   ├── majority.py              # Vote outcome determination
    │   └── refunds.py               # Sender refund logic
    ├── protocol/                 # Protocol definitions
    │   ├── models.py            # Data structures (immutable)
    │   ├── constants.py         # NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES
    │   └── types.py             # Type definitions
    ├── specification/           # Formal specification
    │   ├── invariants/          # System invariants
    │   │   ├── checker.py       # Main invariant checker
    │   │   └── definitions/     # 22 invariant implementations
    │   └── state_machine/       # State machine specification
    │       ├── graph.py         # TRANSACTION_GRAPH definition
    │       └── path_analysis/   # Path analysis tools
    │           ├── path_generator.py
    │           ├── path_counter.py
    │           └── path_filter.py
    ├── display/                 # Visualization utilities
    ├── metrics/                 # Metrics and aggregations
    └── utils.py                 # Utility functions

tests/
├── round_combinations/       # Path generation tests
├── round_labeling/          # Round detection tests
├── fee_distributions/       # Fee distribution tests
│   ├── simple_round_types_tests/
│   └── check_invariants/    # Invariant testing
└── slashing/               # Idleness and violation tests

scripts/                     # Utility scripts
├── 01_generate_test_vectors.py  # Generate compressed JSON files for all paths
├── 02_decode_test_vector.py     # Decode and visualize JSON path files
└── 03_analyze_incentives.py     # Analyze incentive structures
```

## How It Works

### Processing Pipeline

```
1. TRANSITIONS_GRAPH defines valid state transitions
   ↓
2. Path Generator creates sequences like:
   ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "APPEAL_VALIDATOR_SUCCESSFUL", "END"]
   ↓
3. Path-to-Transaction converter creates TransactionRoundResults with appropriate votes
   ↓
4. Round Labeling analyzes vote patterns (content-based, not index-based):
   - All NA votes → Leader Appeal
   - LEADER_TIMEOUT → Leader Timeout
   - AGREE/DISAGREE without leader → Validator Appeal
   ↓
5. Fee Distribution based on labels:
   - NORMAL_ROUND → Leader and majority validators earn
   - APPEAL_*_SUCCESSFUL → Appealant earns bond
   - Special patterns trigger transformations
   ↓
6. Invariant Checking ensures correctness
```

### Round Type Detection

Rounds are identified by their vote patterns, not their position:

- **Leader Appeals**: All participants vote "NA"
- **Validator Appeals**: No LEADER_RECEIPT, validators vote AGREE/DISAGREE
- **Normal Rounds**: Have LEADER_RECEIPT or LEADER_TIMEOUT
- **Special Patterns**: e.g., successful appeal makes previous round SKIP_ROUND

### Key Concepts

1. **Vote Types**:
   - `LEADER_RECEIPT`: Leader submitted result
   - `LEADER_TIMEOUT`: Leader failed to respond
   - `AGREE`/`DISAGREE`/`TIMEOUT`: Validator votes
   - `NA`: Not applicable (appeals)

2. **Round Sizes**:
   - Normal rounds: [5, 11, 23, 47, 95, 191, 383, 767, 1000]
   - Appeal rounds: [7, 13, 25, 49, 97, 193, 385, 769, 1000]

3. **Fee Distribution**:
   - Leader earns: leader_timeout + validator_timeout (if majority)
   - Validators earn: validator_timeout (if in majority)
   - Penalties: PENALTY_REWARD_COEFFICIENT * validator_timeout

## Installation

1. Clone the repository:
    
    ```bash
    git clone <repository_url>
    cd genlayer-fee-distribution-simulator
    ```
    
2. Set up the conda environment:
    
    ```bash
    # Activate miniconda
    source ~/opt/miniconda3/bin/activate
    
    # Create and activate the consensus-simulator environment
    conda create -n consensus-simulator python=3.9
    conda activate consensus-simulator
    ```
    
3. Install dependencies:
    
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Running Tests

To run the entire test suite:

```bash
pytest
```

To run tests with full output logging:

```bash
pytest -s --verbose-output --debug-output > tests.txt 
```

To run a specific test with verbose and debug output (displays formatted tables):

```bash
pytest tests/fee_distributions/simple_round_types_tests/test_normal_round.py -s --verbose-output --debug-output
```

To run round labeling tests with property-based testing:

```bash
pytest tests/round_labeling/test_round_labeling_properties.py -s
```

To run exhaustive path testing (can take hours for long paths):

```bash
python tests/round_labeling/run_path_tests.py
```

### Generate Path JSON Files

Generate compressed JSON files for all possible paths (useful for external verification):

```bash
# Generate all paths up to length 7 (484 paths)
python scripts/01_generate_test_vectors.py --max-length 7

# Generate paths up to length 17 (~113M paths, requires significant time and storage)
python scripts/01_generate_test_vectors.py --max-length 17

# Test mode (generates only 10 paths per length)
python scripts/01_generate_test_vectors.py --max-length 7 --test-mode

# Specify custom output directory
python scripts/01_generate_test_vectors.py --max-length 7 --output-dir custom_output
```

The generated files will be organized in directories by path length:
```
path_jsons/
├── lookup_tables.json      # Decoding tables for compressed format
├── length_03/             # Paths of length 3
│   ├── 02-0cd0354f.json
│   └── ...
├── length_04/             # Paths of length 4
│   └── ...
└── ...
```

### Decode and Visualize Path JSON Files

Decode compressed JSON files and visualize the transaction:

```bash
# Show compressed data summary and summary table (default)
python scripts/02_decode_test_vector.py path_jsons/length_03/02-0cd0354f.json

# Show all visualizations
python scripts/02_decode_test_vector.py path_jsons/length_03/02-0cd0354f.json --show-all

# Show specific visualizations
python scripts/02_decode_test_vector.py path_jsons/length_03/02-0cd0354f.json -t -f
# -c: compressed data summary
# -t: transaction results
# -f: fee distribution details
# -s: summary table
# -a: all visualizations

# Use custom path_jsons directory
python scripts/02_decode_test_vector.py custom_output/length_03/02-0cd0354f.json --json-dir custom_output
```

### Analyze Incentive Structures

Analyze different validator strategies and their financial outcomes:

```bash
# Analyze incentive structures for different path lengths
python scripts/03_analyze_incentives.py --max-length 7

# Generate detailed table of outcomes
python scripts/03_analyze_incentives.py --max-length 5 --show-details
```

### Creating Custom Scenarios

You can create and simulate custom transaction scenarios programmatically:

```python
from src.fee_simulator.protocol.models import TransactionBudget, TransactionRoundResults, Round, Rotation
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.utils import generate_random_eth_address
from src.fee_simulator.display import display_summary_table, display_transaction_results

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(6)]

# Define budget
budget = TransactionBudget(
    leaderTimeout=100,
    validatorsTimeout=200,
    appealRounds=0,
    rotations=[0],
    senderAddress=addresses[5],
    appeals=[],
    staking_distribution="constant"
)

# Define transaction results
rotation = Rotation(
    votes={
        addresses[0]: ["LEADER_RECEIPT", "AGREE"],
        addresses[1]: "AGREE",
        addresses[2]: "AGREE",
        addresses[3]: "AGREE",
        addresses[4]: "DISAGREE"
    }
)
results = TransactionRoundResults(rounds=[Round(rotations=[rotation])])

# Get round labels
round_labels = label_rounds(results)

# Process transaction
fee_events, _ = process_transaction(addresses, results, budget)

# Display results
display_summary_table(fee_events, results, budget, round_labels)
display_transaction_results(results, round_labels)
```

## Testing Framework

The test suite covers:

- **Unit Tests**: Validate individual components (e.g., budget calculations, refunds)
- **Scenario-Based Tests**: Test specific round types (e.g., normal rounds, successful/unsuccessful appeals)
- **Property-Based Tests**: Use Hypothesis to generate test cases for round labeling
- **Path-Based Tests**: Exhaustively test all paths through TRANSITIONS_GRAPH
- **Invariant Tests**: Verify 22 invariants for every test case
- **Slashing Tests**: Verify slashing for idleness and deterministic violations
- **Edge Cases**: Handle empty rounds, undetermined majorities, and consecutive appeals

## Invariants

The system maintains 22 invariants that are checked for every test:

1. Conservation of value
2. Non-negative balances
3. Appeal bond coverage
4. Majority/minority consistency
5. Role exclusivity
6. Sequential processing
7. Appeal follows normal
8. Burn non-negativity
9. Refund non-negativity
10. Vote consistency
11. Idle slashing correctness
12. Deterministic violation slashing
13. Leader timeout earning limits
14. Appeal bond consistency
15. Round size consistency
16. Fee event ordering
17. Stake immutability
18. Round label validity
19. No double penalties
20. Earning justification
21. Cost accounting
22. Slashing proportionality

## Use Cases

- **Economic Analysis**: Evaluate the incentive structure of the GenLayer protocol
- **Protocol Validation**: Simulate fee distribution before deploying protocol changes
- **Consensus Verification**: Generate test data for consensus algorithm implementations
- **Education**: Understand blockchain consensus and fee mechanics
- **Development**: Test and refine fee distribution algorithms

## License

This project is licensed under the MIT License. See the LICENSE file for details.