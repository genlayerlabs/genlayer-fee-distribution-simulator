# Test Architecture Documentation

## Overview

The GenLayer Fee Distribution Simulator employs a comprehensive testing strategy designed to ensure mathematical correctness and production-ready reliability for blockchain financial operations. The test suite uses multiple testing approaches to achieve 100% coverage of all possible transaction scenarios.

## Test Directory Structure

```
tests/
├── __init__.py
├── conftest.py                          # Pytest configuration and global fixtures
│
├── budget_and_refunds/                  # Budget and refund mechanism tests
│   ├── test_budget_computing.py
│   └── test_refunds.py
│
├── fee_distributions/                   # Core fee distribution testing
│   ├── INVARIANTS_DESIGN.md            # 22 invariants documentation
│   ├── check_invariants/               # Invariant implementation
│   │   ├── comprehensive_invariants.py # All 22 invariants
│   │   ├── invariant_checks.py        # Helper functions
│   │   ├── test_invariants_in_round_combinations.py
│   │   └── analyze_tests_results.py   # Test result analysis
│   ├── simple_round_types_tests/       # Individual round type tests
│   │   ├── test_normal_round.py
│   │   ├── test_appeal_leader_successful.py
│   │   ├── test_appeal_leader_unsuccessful.py
│   │   ├── test_appeal_validator_successful.py
│   │   ├── test_appeal_validator_unsuccessful.py
│   │   ├── test_leader_timeout_*.py
│   │   └── test_split_previous_appeal_bond.py
│   └── unit_tests/                     # Unit tests for distribution functions
│       └── test_fee_distribution_functions.py
│
├── round_combinations/                  # Exhaustive path testing
│   ├── README.md                       # Path analysis documentation
│   ├── graph_data.py                   # TRANSITIONS_GRAPH (source of truth)
│   ├── path_generator.py               # DFS path generation
│   ├── path_counter.py                 # Matrix-based counting
│   ├── path_analyzer.py                # Statistical analysis
│   ├── path_display.py                 # Path visualization
│   ├── critical_path_analyzer.py       # Production verification
│   ├── debug_path_differences.py       # Debugging utilities
│   ├── round_combinations.py           # Core combination logic
│   └── test_round_combinations.py      # Path testing
│
├── round_labeling/                     # Round type detection tests
│   ├── README.md                       # Labeling documentation
│   ├── README_COMPREHENSIVE_TESTING.md # Testing strategy
│   ├── pytest.ini                      # Pytest configuration
│   ├── test_round_labeling.py          # Core labeling tests
│   ├── test_round_labeling_advanced.py # Complex scenarios
│   ├── test_round_labeling_properties.py # Property-based testing
│   ├── test_chained_unsuccessful_appeals.py # Consecutive appeals
│   ├── test_path_generation_check.py   # Path verification
│   ├── test_all_paths_comprehensive.py # Exhaustive testing
│   └── run_path_tests.py               # Exhaustive test runner
│
└── slashing/                           # Penalty mechanism tests
    ├── test_deterministic_violation.py # Hash mismatch penalties
    ├── test_idleness.py               # Idle validator penalties
    └── test_tribunal_appeal.py        # Tribunal mechanisms

scripts/                                # Utility scripts
├── generate_path_jsons.py              # Export paths to JSON
└── decode_path_json.py                 # Decode and visualize JSONs
```

## Testing Framework

### Core Framework: Pytest
- Custom command-line options: `--verbose-output`, `--debug-output`
- Fixture-based test organization
- Parametrized test support
- Custom markers for test categorization

### Additional Frameworks
- **Hypothesis**: Property-based testing for round labeling
- **NumPy**: Matrix operations for path counting
- **Tabulate**: Rich table formatting for test output
- **Custom Display Utilities**: Fee distribution visualization

## Testing Approaches

### 1. Unit Testing
**Purpose**: Test individual functions in isolation

**Characteristics**:
- Direct function calls with mock data
- Single responsibility testing
- Fast execution (< 1 second each)
- High granularity

**Example Pattern**:
```python
def test_compute_appeal_bond():
    # Test specific bond calculation
    bond = compute_appeal_bond(
        normal_round_index=0,
        leader_timeout=100,
        validators_timeout=200,
        round_labels=["NORMAL_ROUND", "APPEAL_LEADER_SUCCESSFUL"]
    )
    assert bond == 1500  # 7 * 200 + 100
```

### 2. Integration Testing
**Purpose**: Test complete transaction processing pipelines

**Characteristics**:
- End-to-end transaction flow
- Multiple component interaction
- Real-world scenario simulation
- Invariant verification

**Example Pattern**:
```python
def test_complete_transaction_flow():
    # Setup transaction from path
    path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "APPEAL_VALIDATOR_SUCCESSFUL", "END"]
    transaction_results, budget = path_to_transaction_results(path, addresses)
    
    # Process through pipeline
    labels = label_rounds(transaction_results)
    fee_events, _ = process_transaction(addresses, transaction_results, budget)
    
    # Verify invariants
    check_comprehensive_invariants(fee_events, budget, transaction_results, labels)
```

### 3. Property-Based Testing
**Purpose**: Discover edge cases through random generation

**Characteristics**:
- Hypothesis framework integration
- Automatic shrinking to minimal failing cases
- Mathematical property verification
- Unbounded test case generation

**Example Pattern**:
```python
@given(
    num_rounds=st.integers(min_value=1, max_value=10),
    appeal_pattern=st.lists(st.booleans())
)
def test_round_labeling_properties(num_rounds, appeal_pattern):
    # Generate transaction from parameters
    # Verify properties hold for all inputs
    assert consecutive_appeals_handled_correctly(transaction)
```

### 4. Exhaustive Path Testing
**Purpose**: Test every possible transaction path

**Characteristics**:
- Complete state space exploration
- Dual verification (counting + generation)
- Production-ready guarantees
- JSON export for external verification

**Key Components**:
- **TRANSITIONS_GRAPH**: Source of truth for valid paths
- **Path Counter**: Matrix multiplication for counting
- **Path Generator**: DFS for actual path generation
- **Path Analyzer**: Statistical validation
- **JSON Export**: Compressed format for consensus team

**Statistics**:
- Length 3: 4 paths
- Length 7: 484 paths
- Length 17: ~113M paths

### 5. Invariant Testing
**Purpose**: Ensure mathematical and business rules always hold

**22 Core Invariants**:
1. **Conservation of value**: Total in = Total out
2. **Non-negative balances**: No negative balances
3. **Appeal bond coverage**: Bonds fully distributed
4. **Majority/minority consistency**: Vote counts accurate
5. **Role exclusivity**: One role per participant per round
6. **Sequential processing**: Rounds processed in order
7. **Appeal follows normal**: Appeals only after normal rounds
8. **Burn non-negativity**: Burns are non-negative
9. **Refund non-negativity**: Refunds are non-negative
10. **Vote consistency**: Votes match transaction data
11. **Idle slashing correctness**: Idle penalties applied correctly
12. **Deterministic violation slashing**: Hash mismatches penalized
13. **Leader timeout earning limits**: Bounded leader earnings
14. **Appeal bond consistency**: Bond amounts match round sizes
15. **Round size consistency**: Sizes follow NORMAL/APPEAL arrays
16. **Fee event ordering**: Sequential IDs maintained
17. **Stake immutability**: Stakes don't change
18. **Round label validity**: Only valid labels used
19. **No double penalties**: Single penalty per violation
20. **Earning justification**: All earnings have valid reason
21. **Cost accounting**: All costs accounted for
22. **Slashing proportionality**: Penalties proportional to offense

## Test Organization Patterns

### File Naming Conventions
- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`
- Helper functions: `_helper_*` or utility modules

### Test Structure Template
```python
class TestFeatureArea:
    """Docstring explaining test area"""
    
    def setup_method(self):
        """Per-test setup"""
        self.addresses = [generate_random_eth_address() for _ in range(1000)]
        self.sender_address = self.addresses[999]
        self.appealant_address = self.addresses[998]
    
    def test_specific_scenario(self, verbose, debug):
        """Test docstring explaining scenario"""
        # Arrange
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        transaction_results, budget = path_to_transaction_results(
            path, self.addresses, self.sender_address, self.appealant_address
        )
        
        # Act
        labels = label_rounds(transaction_results)
        fee_events, _ = process_transaction(self.addresses, transaction_results, budget)
        
        # Assert invariants
        check_comprehensive_invariants(fee_events, budget, transaction_results, labels)
        
        # Assert specific outcomes
        assert fee_events[0].earned == expected_value
        
        # Display results if verbose
        if verbose:
            display_summary_table(fee_events, transaction_results, budget, labels)
```

### Common Test Utilities

#### Address Generation
```python
addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[999]
appealant_address = addresses[998]
```

#### Transaction Creation
```python
# From path (recommended)
transaction_results, budget = path_to_transaction_results(
    path=["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
    addresses=addresses,
    sender_address=sender_address,
    appealant_address=appealant_address
)

# Manual creation
transaction = TransactionRoundResults(
    rounds=[Round(rotations=[Rotation(votes={...})])]
)
```

#### Invariant Checking
```python
# Single invariant
assert_conservation_of_value(fee_events, budget)

# All invariants (recommended)
check_comprehensive_invariants(fee_events, budget, transaction_results, labels)
```

## Configuration and Fixtures

### Global Fixtures (conftest.py)
```python
@pytest.fixture
def verbose(request):
    """Enable verbose output when --verbose-output is passed"""
    return request.config.getoption("--verbose-output")

@pytest.fixture
def debug(request):
    """Enable debug output when --debug-output is passed"""
    return request.config.getoption("--debug-output")
```

### Custom Command Options
- `--verbose-output`: Display summary tables and results
- `--debug-output`: Display detailed transaction data

## Test Execution Patterns

### Running Tests
```bash
# All tests
pytest

# Specific directory
pytest tests/fee_distributions/

# Specific file
pytest tests/round_labeling/test_round_labeling.py

# With verbose output
pytest -s --verbose-output --debug-output

# Specific test
pytest tests/fee_distributions/simple_round_types_tests/test_normal_round.py::test_specific_case

# Generate test output file
pytest -s --verbose-output --debug-output > tests.txt

# Run exhaustive path tests
python tests/round_labeling/run_path_tests.py
```

### Test Output
- **Standard**: Pass/fail indicators
- **Verbose**: Formatted tables showing fee distributions
- **Debug**: Complete transaction details and intermediate states
- **File Output**: Results written to test_results/ directory

## Coverage Strategy

### Code Coverage
- Target: 100% line coverage for core logic
- Tool: pytest-cov
- Critical paths must have multiple test approaches

### Scenario Coverage
- All round types (14 different labels)
- All vote combinations
- All appeal patterns
- Edge cases (empty rounds, timeouts, etc.)
- Consecutive appeals (up to 16 chained)

### Path Coverage
- Exhaustive testing up to length 7 (484 paths)
- Statistical sampling for lengths 8-19
- Critical path identification and testing
- JSON export for external verification

## JSON Export and Verification

### Path Export (`scripts/generate_path_jsons.py`)
```bash
# Generate compressed JSONs for all paths
python scripts/generate_path_jsons.py --max-length 7

# Test mode (10 paths per length)
python scripts/generate_path_jsons.py --max-length 7 --test-mode
```

### Path Visualization (`scripts/decode_path_json.py`)
```bash
# Decode and visualize a path
python scripts/decode_path_json.py path_jsons/length_03/02-0cd0354f.json --show-all
```

### JSON Format
- Compressed from 43KB to ~800 bytes per path
- Sequential address numbering
- Bitfield encoding for invariants
- Only active participants included

## Performance Considerations

### Test Execution Time
- Unit tests: < 1 second each
- Integration tests: < 5 seconds each
- Path tests (length 7): ~30 seconds
- Exhaustive tests: May take hours

### Resource Usage
- Memory: Path testing can use significant memory
- CPU: Matrix operations are compute-intensive
- Disk: JSON export requires ~100GB for all paths

## Best Practices

### Test Independence
- Each test must be completely independent
- No shared state between tests
- Deterministic behavior (no random without seed)

### Clear Test Names
- Test names should describe the scenario
- Include expected outcome in name when relevant
- Group related tests in classes

### Assertion Messages
- Include context in assertion messages
- Show actual vs expected values
- Reference invariant numbers when applicable

### Documentation
- Each test file should have a module docstring
- Complex tests need inline comments
- Reference CLAUDE.md for business rules

## Continuous Integration

### Test Stages
1. **Fast Tests**: Unit tests and basic integration (< 5 minutes)
2. **Full Tests**: All tests except exhaustive (< 30 minutes)
3. **Exhaustive Tests**: Complete path verification (nightly)

### Failure Handling
- Tests must fail fast with clear messages
- Invariant violations must identify which invariant failed
- Include transaction state in failure output

## Recent Improvements

### Consecutive Appeal Handling
- Fixed round labeling for chained appeals
- Look back through appeal chain to find original round
- Comprehensive test coverage for appeal patterns

### Path-Based Testing
- TRANSITIONS_GRAPH as single source of truth
- Automatic test generation from graph
- Exhaustive verification of all scenarios

### JSON Export System
- Compressed format for external verification
- Enables consensus team validation
- Efficient storage and transmission

## Future Considerations

### Scalability
- Parallel test execution for path testing
- Distributed testing for exhaustive verification
- Incremental JSON generation

### Maintenance
- Regular review of test coverage
- Update tests when business rules change
- Refactor tests to reduce duplication

### Monitoring
- Track test execution times
- Monitor flaky tests
- Analyze failure patterns
- Dashboard for path coverage visualization