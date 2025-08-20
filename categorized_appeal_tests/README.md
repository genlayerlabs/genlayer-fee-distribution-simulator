# Categorized Appeal Test Cases

This directory contains test cases from length_03 paths categorized by appeal type.

## Directory Structure

```
categorized_appeal_tests/
├── README.md                               # This file
├── summary.json                            # Overall summary statistics
├── compressed/                             # Compressed format files
│   ├── leader_appeal_successful_compressed.json
│   ├── leader_appeal_unsuccessful_compressed.json
│   ├── leader_timeout_appeal_successful_compressed.json
│   ├── leader_timeout_appeal_unsuccessful_compressed.json
│   ├── validator_appeal_successful_compressed.json
│   └── validator_appeal_unsuccessful_compressed.json
├── leader_appeal_successful.json           # Full format
├── leader_appeal_unsuccessful.json         # Full format
├── leader_timeout_appeal_successful.json   # Full format
├── leader_timeout_appeal_unsuccessful.json # Full format
├── validator_appeal_successful.json        # Full format
└── validator_appeal_unsuccessful.json      # Full format
```

## Categories

The test cases are organized into 6 categories based on the appeal type:

1. **validator_appeal_successful** (14 test cases)
   - Scenarios where validators successfully appeal against the majority decision

2. **validator_appeal_unsuccessful** (4 test cases)
   - Scenarios where validators fail to overturn the majority decision

3. **leader_appeal_successful** (8 test cases)
   - Scenarios where the leader successfully appeals

4. **leader_appeal_unsuccessful** (2 test cases)
   - Scenarios where the leader's appeal fails

5. **leader_timeout_appeal_successful** (4 test cases)
   - Scenarios where a leader timeout is successfully appealed

6. **leader_timeout_appeal_unsuccessful** (1 test case)
   - Scenarios where a leader timeout appeal fails

## File Formats

### Full Format (`<category>.json`)
Contains complete test cases with all details:
- Initial state with validators and votes
- Expected rewards and penalties
- Sender outcomes
- Statistical summaries
- Uses simplified addresses (validator1, validator2, sender)

### Compressed Format (`compressed/<category>_compressed.json`)
Contains summarized patterns with:
- Pattern counts
- Example test cases (one per unique pattern)
- Summary statistics for rewards, penalties, and sender outcomes
- Uses simplified addresses (validator1, validator2, sender)

## Generation

To regenerate these categorized files:

```bash
# Generate full categorized files
python3 scripts/05_categorize_appeal_tests.py --pretty

# Generate compressed summaries
python3 scripts/05_categorize_appeal_tests.py --compressed --pretty
```

## Summary Statistics

- **Total test cases**: 33
- **Unique patterns**: 33 (each test case represents a unique path)
- **Categories covered**: 6 appeal types

## Usage

These categorized test files are designed for:
1. Solidity smart contract testing of appeal mechanisms
2. Validation of fee distribution in appeal scenarios
3. Testing edge cases in consensus appeal logic
4. Benchmarking appeal resolution costs