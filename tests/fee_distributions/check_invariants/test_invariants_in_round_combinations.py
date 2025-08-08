import pytest
import itertools
import os
from datetime import datetime
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.specification.state_machine.path_analysis.path_generator import (
    generate_all_paths,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    PathConstraints,
)
from src.fee_simulator.utils import generate_random_eth_address

from src.fee_simulator.display import (
    display_transaction_results,
    display_fee_distribution,
    display_summary_table,
    display_test_description,
)
from src.fee_simulator.specification.invariants.checker import (
    check_all_invariants,
)
from src.fee_simulator.specification.state_machine.graph import TRANSACTION_GRAPH

# Constants
LEADER_TIMEOUT = 100
VALIDATORS_TIMEOUT = 200

# Create output directory
OUTPUT_DIR = "test_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Generate addresses pool
addresses_pool = [generate_random_eth_address() for _ in range(2000)]
sender_address = addresses_pool[1999]
appealant_address = addresses_pool[1998]

# Generate all paths
all_paths = generate_all_paths(
    TRANSACTION_GRAPH,
    PathConstraints(
        min_length=3, max_length=5, source_node="START", target_node="END"
    ),  # not real max length which would be 19
)


def write_test_output(filename, content):
    """Write test output to a file in the OUTPUT_DIR"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w") as f:
        f.write(content)
    return filepath


def capture_display_output(func, *args, **kwargs):
    """Capture the output of display functions"""
    import io
    import sys
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        func(*args, **kwargs)
    return f.getvalue()


slice_size = 50


@pytest.mark.parametrize(
    "path",
    list(itertools.islice(all_paths, slice_size)) if all_paths else [],
    ids=lambda x: f"path_{'-'.join(x) if isinstance(x, list) else str(x)}",
)
def test_paths_with_invariants(verbose, debug, path):
    """
    Test each path from all_paths with comprehensive invariants.

    This test ensures that:
    1. Paths from TRANSITIONS_GRAPH convert properly to TransactionRoundResults
    2. Round labeling works correctly for all valid paths
    3. Fee distribution satisfies all invariants
    """
    test_description = f"Testing transaction path: {' -> '.join(path)}. Verifies round labeling, fee distribution, and invariants."

    # Initialize output content
    output_content = []
    output_content.append(f"TEST PATH: {' -> '.join(path)}")
    output_content.append(f"Timestamp: {datetime.now().isoformat()}")
    output_content.append("=" * 80)
    output_content.append("")

    success = False
    error_message = ""

    try:
        # Convert path to transaction results using the new converter
        transaction_results, transaction_budget = path_to_transaction_results(
            path=path,
            addresses=addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=LEADER_TIMEOUT,
            validators_timeout=VALIDATORS_TIMEOUT,
        )

        # Get round labels
        round_labels = label_rounds(transaction_results)

        # Process transaction
        fee_events, _ = process_transaction(
            addresses=addresses_pool,
            transaction_results=transaction_results,
            transaction_budget=transaction_budget,
        )

        # Capture outputs
        output_content.append("ROUND LABELS:")
        output_content.append(str(round_labels))
        output_content.append("")

        output_content.append("PATH NODES (excluding START/END):")
        output_content.append(str(path[1:-1]))
        output_content.append("")

        output_content.append("SUMMARY TABLE:")
        summary_output = capture_display_output(
            display_summary_table,
            fee_events,
            transaction_results,
            transaction_budget,
            round_labels,
        )
        output_content.append(summary_output)
        output_content.append("")

        output_content.append("TRANSACTION RESULTS:")
        results_output = capture_display_output(
            display_transaction_results, transaction_results, round_labels
        )
        output_content.append(results_output)
        output_content.append("")

        if debug:
            output_content.append("FEE DISTRIBUTION:")
            fee_output = capture_display_output(display_fee_distribution, fee_events)
            output_content.append(fee_output)
            output_content.append("")

        # Check comprehensive invariants
        output_content.append("INVARIANT CHECK:")
        try:
            check_all_invariants(
                fee_events,
                transaction_budget,
                transaction_results,
                round_labels,
                tolerance=20,
            )
            output_content.append("✓ All invariants passed")
            success = True
        except AssertionError as e:
            error_message = str(e)
            output_content.append(f"✗ Invariant failed: {error_message}")
            success = False
        except Exception as e:
            error_message = f"{type(e).__name__}: {str(e)}"
            output_content.append(
                f"✗ Unexpected error in invariant check: {error_message}"
            )
            success = False

    except Exception as e:
        error_message = f"{type(e).__name__}: {str(e)}"
        output_content.append(f"✗ Test failed with error: {error_message}")
        import traceback

        output_content.append("")
        output_content.append("TRACEBACK:")
        output_content.append(traceback.format_exc())
        success = False

    # Generate filename
    status_prefix = "S" if success else "F"
    safe_path_name = "_".join(
        path[:3]
    )  # Use first 3 elements to keep filename reasonable
    if len(path) > 3:
        safe_path_name += f"_plus{len(path)-3}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
    filename = f"{status_prefix}_{safe_path_name}_{timestamp}.txt"

    # Write output
    full_content = "\n".join(output_content)
    filepath = write_test_output(filename, full_content)

    # Print summary to console
    status_symbol = "✓" if success else "✗"
    print(f"{status_symbol} {' -> '.join(path)} -> {filepath}")

    # If verbose, also display in console
    if verbose:
        display_test_description(
            test_name=f"test_path_{'-'.join(path)}",
            test_description=test_description,
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Re-raise the error to mark test as failed
    if not success:
        pytest.fail(f"Test failed: {error_message}")
