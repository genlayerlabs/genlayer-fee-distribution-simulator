# Round Combinations Analysis System

A critical system for analyzing all possible transaction paths in a blockchain fee distribution system. This system provides 100% accurate verification with zero approximation, suitable for production blockchain environments.

## Overview

This system analyzes transaction paths through a directed graph representing possible state transitions in a blockchain consensus mechanism. It's designed to verify fee distribution logic by examining ALL possible paths without sampling or approximation.

### Key Features

- **100% Complete Analysis**: Processes every single possible path
- **Memory Efficient**: Uses lazy generation to handle millions of paths
- **Dual Verification**: Matrix counting + DFS generation for verification
- **Critical System Ready**: Designed for blockchain production use
- **Cycle Support**: Handles graphs with cycles (repeated nodes allowed)

## Important Concepts

### Path Length Definition
**CRITICAL**: Path length is measured in **edges** (transitions), not nodes.
- A path with 4 nodes has 3 edges
- This matches standard graph theory conventions
- Both matrix and DFS methods use this definition

### Paths vs Simple Paths
- **Paths**: Can revisit nodes (cycles allowed) - this is what we count
- **Simple Paths**: No repeated nodes - available via `generate_simple_paths()`

## Module Structure

### Core Data Types

#### `path_types.py`
```python
- NodeName: Type alias for node names
- Path: List of nodes representing a path
- Graph: Adjacency list representation
- PathConstraints: Immutable constraints for path search
- PathStatistics: Statistics about path collections
- CountingResult: Result from matrix counting
```

### Data Module

#### `graph_data.py`
- Pure data: the transaction graph structure
- Immutable view using `MappingProxyType`
- No behavior, just the graph definition
- Contains the blockchain state transition graph

### Algorithm Modules

#### `path_counter.py`
- Adjacency matrix-based path counting
- Uses matrix exponentiation for efficiency
- O(n³ × k) complexity where n = nodes, k = max path length
- Counts paths with cycles

#### `path_generator.py`
- DFS-based path generation
- Two modes:
  - `generate_all_paths()`: Returns all paths (can use lots of memory)
  - `generate_paths_lazy()`: Generator for memory efficiency
- Supports both paths with cycles and simple paths

#### `path_analyzer.py`
- Statistical analysis of path collections
- Pattern detection and categorization
- Frequency analysis
- Extreme path identification

### Display Module

#### `path_display.py`
- All presentation and formatting logic
- Progress reporting for long operations
- Statistics display
- Path formatting utilities

### Orchestration Modules

#### `round_combinations.py`
- High-level analysis workflows
- Combines counting, generation, and analysis
- Standard use cases

#### `round_combinations_critical.py`
- **For production blockchain systems**
- Processes ALL paths without storing in memory
- Verification against matrix counting
- Checkpoint support for long runs
- Critical error detection

## Usage Examples

### Basic Analysis (Small Path Sets)
```python
from path_types import PathConstraints
from round_combinations import TransactionPathAnalyzer

# For smaller constraints (< 1M paths)
constraints = PathConstraints(
    min_length=3,
    max_length=10,
    source_node="START",
    target_node="END"
)

analyzer = TransactionPathAnalyzer(constraints)
paths, summary = analyzer.run_complete_analysis()
```

### Critical Blockchain Verification (Large Path Sets)
```python
from path_types import PathConstraints
from round_combinations_critical import CriticalPathAnalyzer

# For production blockchain verification
constraints = PathConstraints(
    min_length=3,
    max_length=19,  # Can result in millions of paths
    source_node="START",
    target_node="END"
)

analyzer = CriticalPathAnalyzer(constraints)

# Process ALL paths with verification
stats, verification_passed = analyzer.run_complete_verification()

if not verification_passed:
    raise RuntimeError("CRITICAL: Blockchain verification failed!")
```

### Quick Path Counting
```python
from path_counter import count_paths_between_nodes

# Just count without generating
result = count_paths_between_nodes(
    TRANSACTION_GRAPH,
    constraints,
    verbose=True
)
print(f"Total paths: {result.count:,}")
```

### Memory-Efficient Processing
```python
from path_generator import generate_paths_lazy

# Process paths one at a time
path_count = 0
for path in generate_paths_lazy(TRANSACTION_GRAPH, constraints):
    # Process each path
    path_count += 1
    # Your processing logic here
```

### Pattern Analysis
```python
from path_analyzer import group_paths_by_feature

# Group paths by number of appeals
appeal_groups = group_paths_by_feature(
    paths,
    lambda p: sum(1 for node in p if "APPEAL" in node)
)

# Find paths with specific patterns
timeout_paths = [
    p for p in paths 
    if any("TIMEOUT" in node for node in p)
]
```

## Performance Considerations

### Memory Usage
- Path storage: ~100 bytes per path (varies by length)
- 1M paths ≈ 100 MB
- 84M paths ≈ 8.4 GB (use lazy generation!)

### Time Complexity
- Matrix counting: O(n³ × k) - Very fast
- DFS generation: O(total_paths) - Can be slow for large sets
- For 84M paths: Expect 2-6 hours depending on CPU

### Recommendations
1. **Always count first** using matrix method to know what to expect
2. **Use lazy generation** for > 1M paths
3. **Set up checkpoints** for very long runs
4. **Monitor memory** usage during execution
5. **Use `round_combinations_critical.py`** for production systems

## Testing

```bash
# Run all tests
python test_round_combinations.py

# Verify specific graph
python debug_path_differences.py

# Check length definitions
python check_length_definition.py
```

## Blockchain-Specific Features

This system is designed for critical blockchain infrastructure:

1. **Zero Tolerance for Errors**: All paths must be verified
2. **Deterministic Results**: Same input always produces same output
3. **Complete Coverage**: No sampling or approximation
4. **Audit Trail**: Checkpoint files for interrupted runs
5. **Verification**: Dual-method verification (matrix + DFS)

## Common Issues and Solutions

### "Mismatch between counting methods!"
- Ensure both methods use same length definition (edges, not nodes)
- Check that DFS allows cycles (no visited set restriction)

### Out of Memory
- Use `generate_paths_lazy()` instead of `generate_all_paths()`
- Use `CriticalPathAnalyzer` for large path sets
- Process in chunks with smaller length constraints

### Slow Performance
- This is expected for millions of paths
- Use matrix counting if you only need totals
- Consider parallel processing (future enhancement)

## Graph Structure

The system analyzes paths through a transaction state graph where:
- Nodes represent transaction states
- Edges represent valid transitions
- Cycles are allowed (states can repeat)
- Special nodes: START and END

Example states:
- `LEADER_RECEIPT_MAJORITY_AGREE`
- `VALIDATOR_APPEAL_SUCCESSFUL`
- `LEADER_TIMEOUT`

## Future Enhancements

1. **Parallel Processing**: Distribute path generation across cores
2. **Graph Visualization**: Visual path exploration
