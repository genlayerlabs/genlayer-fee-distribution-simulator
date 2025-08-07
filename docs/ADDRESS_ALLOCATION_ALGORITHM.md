# Address Allocation Algorithm for Consensus Rounds

## Overview

This document describes the address allocation algorithm for consensus rounds in the fee distribution system. The algorithm determines which addresses participate in each round based on the round type (normal or appeal) and the history of previous rounds.

## Round Size Constants

### Normal Round Sizes (Even Blockchain Indices)
```python
NORMAL_ROUND_SIZES = [
    5,    # Round 0 (blockchain index 0)
    11,   # Round 1 (blockchain index 2)
    23,   # Round 2 (blockchain index 4)
    47,   # Round 3 (blockchain index 6)
    95,   # Round 4 (blockchain index 8)
    191,  # Round 5 (blockchain index 10)
    383,  # Round 6 (blockchain index 12)
    767,  # Round 7 (blockchain index 14)
    1000, # Round 8+ (blockchain index 16+)
]
```

### Appeal Round Sizes (Odd Blockchain Indices)
```python
APPEAL_ROUND_SIZES = [
    7,    # Appeal 0 (blockchain index 1)
    13,   # Appeal 1 (blockchain index 3)
    25,   # Appeal 2 (blockchain index 5)
    49,   # Appeal 3 (blockchain index 7)
    97,   # Appeal 4 (blockchain index 9)
    193,  # Appeal 5 (blockchain index 11)
    385,  # Appeal 6 (blockchain index 13)
    769,  # Appeal 7 (blockchain index 15)
    1000, # Appeal 8+ (blockchain index 17+)
]
```

## Address Pool

- Total available addresses: 1000 (indices 0-999)
- Addresses are pulled from this pool based on the rules below
- Once an address is used, it remains in the "active set" for potential reuse unless explicitly removed

## Core Rules

### 1. Normal Rounds

Normal rounds reuse addresses from the **cumulative active set** of all previous rounds:

- **First normal round (index 0)**: Uses addresses 0 to 4 (5 addresses)
- **Subsequent normal rounds**: 
  - Reuse ALL addresses that have participated in ANY previous round (normal or appeal)
  - Add new addresses if needed to reach the required size
  - The leader is always the first address in the round's address list
  - Remove the leaders of the previous normal rounds
  - The new leader should always be the smallest index in the cumulative active set

### 2. Appeal Rounds

Appeal round sizes are determined by the previous round:

#### 2.1 Appeal Following a Normal Round
- Size: Same index in APPEAL_ROUND_SIZES as the current round index in NORMAL_ROUND_SIZES
- Addresses: Pull entirely NEW addresses that haven't been used yet
- Example: After a normal round with 5 addresses (0-4), an appeal would use addresses 5-11 (7 new addresses)

#### 2.2 Appeal Following an Unsuccessful Appeal
- Size: Same index in APPEAL_ROUND_SIZES as the current round index in NORMAL_ROUND_SIZES - 2
- Addresses: Pull entirely NEW addresses that haven't been used yet
- This creates a "shrinking" effect for consecutive unsuccessful appeals

## Address Allocation Examples

### Example 1: Simple Path (Normal → Appeal → Normal)
```
Round 0 (Normal, size 5): addresses [0, 1, 2, 3, 4]
Round 1 (Appeal from normal, size 7): addresses [5, 6, 7, 8, 9, 10, 11]
Round 2 (Normal, size 11): addresses [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
```
- Round 2 reuses all 12 previously used addresses but only needs 11

### Example 2: Complex Path with Mixed Appeals
```
Round 0 (Normal, size 5): addresses [0, 1, 2, 3, 4]
Round 1 (Appeal from normal, size 7): addresses [5, 6, 7, 8, 9, 10, 11]
Round 2 (Unsuccessful appeal, size 11): addresses [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22] 
Round 3 (Successful appeal, size 23): addresses [23, 24, 25, 26, 27, 28, 29, 30, 31, ... , 46] 
Round 4 (Normal, size 47): addresses [1, 2, 3, 4, ... 46, 47] (pulled one new address to reach 47 which is the size we should use)
```

## Edge Cases

### Edge Case 1: Address Pool Exhaustion
- If the required size exceeds available addresses, use all remaining addresses
- Example: Need 1000 addresses but only 950 are available → use all 950

### Edge Case 2: Leader Selection in Normal Rounds
- The leader is always at index 0 of the round's address list
- For the first normal round, this is address 0
- For subsequent normal rounds, this is the first address in the cumulative set (removing previous leaders) so for next normal round, leader will likely be index 1, then 2, etc.
- But can happen that some addresses have been removed from active validators set, because were IDLE or have been slashed or whatever, so must be lowest available index, not necessarily index 1.

### Edge Case 3: Very Long Appeal Chains
- With 8 consecutive unsuccessful appeals, sizes would be: 7, 11, 23, 47, 95, 191, 383, 767
- This would consume 5+7+11+23+47+95+191+383+(1000-762=238) = 1000 addresses (last appeal is 238 which is smaller than 383)
- System must handle gracefully by using remaining available addresses

### Edge Case 4: Removed Addresses (IDLE/Slashed)
- Addresses can be removed from the active validator set due to:
  - IDLE votes (validator didn't participate)
  - Deterministic violations (hash mismatches)
  - Other slashing conditions
- These addresses should not be included in subsequent rounds
- Implementation needs to track a "blacklist" of removed addresses

## Implementation Notes

### State Tracking
The implementation needs to maintain several pieces of state:

1. **Cumulative Active Set**: All addresses that have ever participated (Set)
2. **Next Unused Address Index**: For pulling new addresses efficiently (Integer)
3. **Previous Normal Leaders**: List of addresses that were leaders in normal rounds (List)
4. **Removed Addresses**: Blacklist of IDLE/slashed addresses (Set)
5. **Round History**: Track round types and outcomes for proper appeal sizing

### Key Data Structures
```python
state = {
    "cumulative_active_set": set(),  # All addresses ever used
    "next_unused_index": 0,           # Next address to pull from pool
    "previous_normal_leaders": [],    # Leaders from normal rounds
    "removed_addresses": set(),       # IDLE/slashed addresses
    "appeal_count": 0,                # Number of appeals so far
    "normal_count": 0,                # Number of normal rounds so far
}
```

### Address Ordering
- **Normal rounds**: Sort addresses by their numeric index (ascending)
- **Appeal rounds**: Maintain the order they were pulled from the pool
- **Leader placement**: Always at index 0 of the round's address list

## Algorithm Pseudocode

```python
def allocate_addresses(path, address_pool, removed_addresses=None):
    """
    Allocate addresses for all rounds in a transaction path.
    
    Args:
        path: List of round types (e.g., ["NORMAL", "APPEAL_UNSUCCESSFUL", "APPEAL_SUCCESSFUL", "NORMAL"])
        address_pool: List of available addresses (typically 1000)
        removed_addresses: Set of addresses that have been slashed/removed
    
    Returns:
        List of address allocations for each round
    """
    if removed_addresses is None:
        removed_addresses = set()
    
    allocations = []
    state = {
        'cumulative_active': set(),
        'next_unused_idx': 0,
        'previous_leaders': [],
        'normal_count': 0,
        'appeal_count': 0
    }
    
    for i, round_type in enumerate(path):
        if is_normal_round(round_type):
            addresses = allocate_normal_round(state, address_pool, removed_addresses)
            state['normal_count'] += 1
        else:
            prev_was_unsuccessful = (i > 0 and 
                                   is_appeal_round(path[i-1]) and 
                                   "UNSUCCESSFUL" in path[i-1])
            addresses = allocate_appeal_round(state, address_pool, removed_addresses, 
                                            prev_was_unsuccessful)
            state['appeal_count'] += 1
        
        allocations.append(addresses)
        state['cumulative_active'].update(addresses)
    
    return allocations

def allocate_normal_round(state, address_pool, removed_addresses):
    """Allocate addresses for a normal round."""
    # Calculate blockchain index and size
    blockchain_idx = state['normal_count'] * 2
    size = NORMAL_ROUND_SIZES[min(blockchain_idx // 2, len(NORMAL_ROUND_SIZES) - 1)]
    
    # Get available addresses (cumulative minus leaders and removed)
    available = (state['cumulative_active'] - 
                set(state['previous_leaders']) - 
                removed_addresses)
    
    # Sort for deterministic selection
    sorted_available = sorted(available)
    
    # If first round or not enough addresses, pull new ones
    if state['normal_count'] == 0:
        addresses = pull_new_addresses(state, address_pool, removed_addresses, size)
    else:
        if len(sorted_available) >= size:
            addresses = sorted_available[:size]
        else:
            # Use all available and pull new ones
            addresses = sorted_available
            needed = size - len(addresses)
            new_addrs = pull_new_addresses(state, address_pool, removed_addresses, needed)
            addresses.extend(new_addrs)
            addresses.sort()
    
    # Record leader (first address)
    if addresses:
        state['previous_leaders'].append(addresses[0])
    
    return addresses

def allocate_appeal_round(state, address_pool, removed_addresses, prev_was_unsuccessful):
    """Allocate addresses for an appeal round."""
    # Calculate size based on appeal count and previous round
    appeal_idx = state['appeal_count']
    base_size = APPEAL_ROUND_SIZES[min(appeal_idx, len(APPEAL_ROUND_SIZES) - 1)]
    
    # Reduce by 2 if previous was unsuccessful appeal
    size = base_size - 2 if prev_was_unsuccessful else base_size
    
    # Always pull new addresses for appeals
    addresses = pull_new_addresses(state, address_pool, removed_addresses, size)
    
    return addresses

def pull_new_addresses(state, address_pool, removed_addresses, count):
    """Pull new addresses from the pool."""
    new_addresses = []
    
    while len(new_addresses) < count and state['next_unused_idx'] < len(address_pool):
        addr = address_pool[state['next_unused_idx']]
        state['next_unused_idx'] += 1
        
        if addr not in removed_addresses:
            new_addresses.append(addr)
    
    return new_addresses

def is_normal_round(round_type):
    """Check if a round type is normal (not appeal)."""
    return "APPEAL" not in round_type

def is_appeal_round(round_type):
    """Check if a round type is appeal."""
    return "APPEAL" in round_type
```

## Special Considerations

### Deterministic Address Selection
- The algorithm must be deterministic given the same path
- Address selection should not depend on randomness
- The same path should always produce the same address allocation

### Testing Requirements
- Test paths with up to 8 consecutive unsuccessful appeals
- Verify address pool exhaustion handling
- Ensure proper leader rotation in normal rounds
- Validate shrinking behavior in appeal chains

## Validation and Testing Scenarios

### Scenario 1: Basic Path (N → A → N)
```python
path = ["NORMAL", "APPEAL", "NORMAL"]
expected = [
    [0, 1, 2, 3, 4],           # Round 0: size 5
    [5, 6, 7, 8, 9, 10, 11],   # Round 1: size 7 (new addresses)
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # Round 2: size 11 (cumulative minus leader 0)
]
```

### Scenario 2: Consecutive Unsuccessful Appeals
```python
path = ["NORMAL", "APPEAL_UNSUCCESSFUL", "APPEAL_UNSUCCESSFUL", "APPEAL_SUCCESSFUL", "NORMAL"]
expected = [
    [0, 1, 2, 3, 4],                     # Round 0: size 5
    [5, 6, 7, 8, 9, 10, 11],             # Round 1: size 7
    [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],  # Round 2: size 11 (13-2)
    [23, 24, ..., 45],                   # Round 3: size 23 (25-2)
    [1, 2, 3, 4, 5, ..., 45, 46, 47]    # Round 4: size 47 (all cumulative minus leader 0)
]
```

### Scenario 3: Address Pool Exhaustion
```python
# 8 consecutive unsuccessful appeals following a normal round
path = ["NORMAL"] + ["APPEAL_UNSUCCESSFUL"] * 7 + ["APPEAL_SUCCESSFUL"]
# Sizes: 5, 7, 11, 23, 47, 95, 191, 383, (remainder)
# Total needed: 5 + 7 + 11 + 23 + 47 + 95 + 191 + 383 + (1000-762) = 1000
```

### Validation Functions

```python
def validate_allocation(path, allocations, address_pool_size=1000):
    """
    Validate that address allocations follow all rules.
    
    Returns: (is_valid, error_message)
    """
    cumulative_active = set()
    previous_leaders = []
    appeal_count = 0
    normal_count = 0
    
    for i, (round_type, addresses) in enumerate(zip(path, allocations)):
        # Check 1: No duplicates within round
        if len(addresses) != len(set(addresses)):
            return False, f"Round {i} has duplicate addresses"
        
        # Check 2: All addresses within pool bounds
        if any(addr >= address_pool_size or addr < 0 for addr in addresses):
            return False, f"Round {i} has addresses outside pool"
        
        if is_normal_round(round_type):
            # Check 3: Normal rounds exclude previous leaders
            for leader in previous_leaders:
                if leader in addresses:
                    return False, f"Round {i} includes previous leader {leader}"
            
            # Check 4: Normal rounds use cumulative addresses first
            if normal_count > 0:
                available = cumulative_active - set(previous_leaders)
                for addr in addresses:
                    if addr < max(cumulative_active, default=-1):
                        if addr not in available:
                            return False, f"Round {i} uses non-cumulative address {addr}"
            
            # Check 5: Correct size
            blockchain_idx = normal_count * 2
            expected_size = NORMAL_ROUND_SIZES[min(blockchain_idx // 2, len(NORMAL_ROUND_SIZES) - 1)]
            if len(addresses) != min(expected_size, address_pool_size - len(previous_leaders)):
                return False, f"Round {i} has wrong size: {len(addresses)} vs {expected_size}"
            
            # Record leader
            if addresses:
                previous_leaders.append(addresses[0])
            normal_count += 1
            
        else:  # Appeal round
            # Check 6: Appeal rounds use only new addresses
            for addr in addresses:
                if addr in cumulative_active:
                    return False, f"Appeal round {i} reuses address {addr}"
            
            # Check 7: Correct appeal size
            prev_unsuccessful = (i > 0 and is_appeal_round(path[i-1]) and "UNSUCCESSFUL" in path[i-1])
            base_size = APPEAL_ROUND_SIZES[min(appeal_count, len(APPEAL_ROUND_SIZES) - 1)]
            expected_size = base_size - 2 if prev_unsuccessful else base_size
            
            # Account for pool exhaustion
            max_available = address_pool_size - len(cumulative_active)
            expected_size = min(expected_size, max_available)
            
            if len(addresses) != expected_size:
                return False, f"Appeal round {i} has wrong size: {len(addresses)} vs {expected_size}"
            
            appeal_count += 1
        
        cumulative_active.update(addresses)
    
    return True, "Valid allocation"

def generate_test_report(test_cases):
    """Generate a test report for multiple allocation scenarios."""
    for name, path, expected in test_cases:
        # Run allocation
        addresses = allocate_addresses(path, list(range(1000)))
        
        # Validate
        is_valid, error = validate_allocation(path, addresses)
        
        # Compare with expected if provided
        matches_expected = addresses == expected if expected else "N/A"
        
        print(f"\nTest: {name}")
        print(f"Path: {' → '.join(path)}")
        print(f"Valid: {is_valid} ({error if not is_valid else 'OK'})")
        print(f"Matches Expected: {matches_expected}")
        
        # Show allocation summary
        for i, (round_type, addrs) in enumerate(zip(path, addresses)):
            if len(addrs) > 10:
                display = f"[{addrs[0]}, {addrs[1]}, ..., {addrs[-2]}, {addrs[-1]}]"
            else:
                display = str(addrs)
            print(f"  Round {i} ({round_type}): {display} (size: {len(addrs)})")
```

## Summary

The address allocation algorithm ensures fair and deterministic participant selection across consensus rounds:

1. **Normal rounds** build upon previous participation, excluding past leaders to ensure rotation
2. **Appeal rounds** always bring in fresh participants to ensure unbiased judgment
3. **Unsuccessful appeals** reduce the appeal size by 2, creating economic pressure
4. **Address pool** is finite (1000), creating natural limits on extended disputes
5. **Removed addresses** (IDLE/slashed) are permanently excluded from future rounds
