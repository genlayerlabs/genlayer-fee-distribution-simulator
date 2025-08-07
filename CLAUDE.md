# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Environment Setup

First run cwd to know where you are. 

If you are in a MacOS, then:

```bash
# Activate the conda environment
source /Users/{username}/opt/miniconda3/bin/activate
conda activate consensus-simulator

# Install dependencies
pip install -r requirements.txt
```

If you are in a Linux:
```bash
# Activate the conda environment
source /home/{username}/miniconda3/bin/activate
conda activate consensus-simulator

# Install dependencies
pip install -r requirements.txt
```

### Run Tests
```bash
# Run all tests
pytest

# Run all tests with full output logging
pytest -s --verbose-output --debug-output > tests.txt

# Run specific test file with verbose tables
pytest tests/round_types_tests/test_normal_round.py -s --verbose-output --debug-output

# Run a single test function
pytest tests/round_types_tests/test_normal_round.py::test_normal_round_single_rotation -s --verbose-output --debug-output

# Run round labeling tests with property-based testing
pytest tests/round_labeling/test_round_labeling_properties.py -s

# Run path analysis tests
pytest tests/round_combinations/test_round_combinations.py -s

# Run fee distribution tests with invariant checking
pytest tests/fee_distributions/ -s --verbose-output

# Run exhaustive path testing (can take hours for long paths)
python tests/round_labeling/run_path_tests.py
```

### Testing Flags
- `--verbose-output`: Displays summary tables showing fee distributions
- `--debug-output`: Shows detailed transaction results and fee event tables
- `-s`: Shows print statements during test execution

## Architecture Overview

### Critical Source of Truth: TRANSITIONS_GRAPH

The `_GRAPH_DATA = TRANSITIONS_GRAPH` in `tests/round_combinations/graph_data.py` is the **definitive source of truth** for all possible state transitions in the system. This directed graph defines:
- All valid transaction states (nodes)
- All possible transitions between states (edges)
- The complete state machine for the fee distribution protocol

**IMPORTANT**: All tests should be generated from this graph structure. The system follows a path-based approach:
1. TRANSITIONS_GRAPH defines valid paths
2. Paths are converted to TransactionRoundResults
3. Content-based round labeling (NOT index-based)
4. Fee distribution based on labels

### Path-Based Flow (After Refactoring)

The system now follows a deterministic path-based flow:

```
TRANSITIONS_GRAPH → Path → TransactionRoundResults → Round Labels → Fee Distribution
```

Key changes from the refactor:
- **No index-based appeal detection**: Appeals are detected by vote patterns, not `i % 2`
- **Content-based round detection**: Round types determined by analyzing votes
- **Split round sizes**: `NORMAL_ROUND_SIZES` and `APPEAL_ROUND_SIZES` for clearer logic
- **Path-to-transaction converter**: `path_to_transaction.py` creates proper vote structures

### Core Transaction Processing Flow

The fee distribution system processes blockchain transactions through a pipeline defined in `fee_simulator/core/transaction_processing.py`:

1. **Stake Initialization**: All participants start with constant stakes
2. **Cost Deduction**: Total transaction cost is deducted from the sender
3. **Idle Handling**: Idle validators are replaced by reserves and slashed (`core/idleness.py`)
4. **Violation Handling**: Validators with hash mismatches are slashed (`core/deterministic_violation.py`)
5. **Round Labeling**: Each round gets labeled based on voting patterns (`core/round_labeling.py`)
   - Uses `is_likely_appeal_round()` for content-based detection
   - No dependency on round indices
6. **Fee Distribution**: Fees are distributed according to round type (`core/round_fee_distribution/`)
7. **Refunds**: Sender receives refunds for unused budget (`core/refunds.py`)

### Key Data Models

**Transaction Structure** (`models.py`):
- `TransactionBudget`: Contains leader/validator timeouts, appeals, sender address
- `TransactionRoundResults`: Contains rounds with rotations and votes
- `Round`: Contains one or more rotations
- `Rotation`: Contains votes from all participants
- `FeeEvent`: Immutable record of fee changes (cost, earned, burn, slash)
- `Appeal`: Contains appealant address for tracking who initiated appeal

**Vote Types** (`types.py`):
- Validator votes: `AGREE`, `DISAGREE`, `TIMEOUT`, `IDLE`
- Leader actions: `LEADER_RECEIPT`, `LEADER_TIMEOUT`
- Appeal votes: `NA` (Not Applicable)
- Votes can include hashes for validation

**Round Labels** (`types.py`):
- Normal execution: `NORMAL_ROUND`, `SKIP_ROUND`
- Appeals: `APPEAL_LEADER_SUCCESSFUL`, `APPEAL_VALIDATOR_UNSUCCESSFUL`, etc.
- Timeouts: `LEADER_TIMEOUT_50_PERCENT`, `LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND`
- Special: `SPLIT_PREVIOUS_APPEAL_BOND`, `EMPTY_ROUND`

### Round Detection Rules (Content-Based)

From `round_labeling.py`:
- **Leader Appeals**: All participants vote "NA"
- **Validator Appeals**: No LEADER_RECEIPT, validators vote AGREE/DISAGREE
- **Leader Timeout**: Has LEADER_TIMEOUT vote (NOT an appeal)
- **Normal Round**: Has LEADER_RECEIPT or is LEADER_TIMEOUT
- **Special Patterns**: Transform labels based on sequences (e.g., successful appeal → previous becomes SKIP_ROUND)

### Fee Distribution Rules

Each round type has specific distribution logic in `fee_simulator/core/round_fee_distribution/`:
- `normal_round.py`: Standard round where majority validators earn fees
- `appeal_leader_successful.py`: Leader wins appeal, gets bond + fees
- `appeal_validator_successful.py`: Validators win, split bond + fees
- `leader_timeout_*.py`: Various timeout scenarios with different fee splits
- `split_previous_appeal_bond.py`: Undetermined outcome after unsuccessful appeal

All distribution functions now:
- Count actual appeal rounds (not `floor(i/2)`)
- Find previous normal rounds by searching backwards
- Use proper round sizes from split constants

### Testing Structure

Tests are organized by functionality:
- `tests/round_types_tests/`: Tests for each round type's fee distribution
- `tests/slashing/`: Tests for idleness and violation penalties
- `tests/budget_and_refunds/`: Tests for cost calculations and refunds
- `tests/invariant_checks.py`: Contains assertion helpers for common invariants
- `tests/round_labeling/`: Comprehensive testing of the round labeling function
  - Property-based testing with Hypothesis
  - Exhaustive path testing
  - Chained appeal scenarios
- `tests/round_combinations/`: Path analysis system for transitions graph
  - Analyzes all possible paths through the state machine
  - Matrix-based counting and DFS generation
  - Critical path verification for blockchain systems
  - Contains `graph_data.py` with TRANSITIONS_GRAPH - the source of truth
- `tests/fee_distributions/`: Comprehensive fee distribution tests
  - `unit_tests/`: Unit tests for each distribution function
  - `check_invariants/`: 22 invariants for correctness
  - Integration tests with full paths

### Important Constants

From `constants.py` (after refactoring):
```python
# Split round sizes for clarity
NORMAL_ROUND_SIZES = [5, 11, 23, 47, 95, 191, 383, 767, 1000]
APPEAL_ROUND_SIZES = [7, 13, 25, 49, 97, 193, 385, 769, 1000]

# Penalty coefficients
PENALTY_REWARD_COEFFICIENT = 1
IDLE_PENALTY_COEFFICIENT = 10
DETERMINISTIC_VIOLATION_PENALTY_COEFFICIENT = 100
```

### Invariants (22 Total)

The system maintains critical invariants checked in `comprehensive_invariants.py`:
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
...and 7 more

### Recent Refactors

1. **ROUND_SIZES Split**: Separated into NORMAL_ROUND_SIZES and APPEAL_ROUND_SIZES
2. **Index-based to Content-based**: Removed all `i % 2` logic for appeals
3. **Path-based Testing**: TRANSITIONS_GRAPH → paths → tests
4. **Appeal Index Calculation**: Count actual appeals, not assume alternating

### Key Utilities

- `utils_round_sizes.py`: Helper functions for round size lookups
- `path_to_transaction.py`: Converts graph paths to TransactionRoundResults
- `bond_computing.py`: Calculates appeal bonds based on round history
- `refunds.py`: Computes sender refunds for unused budget

### Vote Pattern Examples

**Leader Appeal (all NA)**:
```python
{
    "0x1": "NA",
    "0x2": "NA", 
    "0x3": "NA"
}
```

**Validator Appeal (no leader receipt)**:
```python
{
    "0x1": "AGREE",
    "0x2": "DISAGREE",
    "0x3": "DISAGREE"
}
```

**Undetermined Votes (1/3 each)**:
- 1/3 AGREE
- 1/3 DISAGREE  
- 1/3 TIMEOUT

TODO: refactor the debug/ folder into new types of tests. Some that are very specific, just delete.