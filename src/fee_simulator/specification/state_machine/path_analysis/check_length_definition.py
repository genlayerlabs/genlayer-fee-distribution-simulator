"""
Check if the issue is with how we define path length.
"""

from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    PathConstraints,
)
from src.fee_simulator.specification.state_machine.graph import TRANSACTION_GRAPH
from src.fee_simulator.specification.state_machine.path_analysis.path_counter import (
    count_paths_between_nodes,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_generator import (
    generate_all_paths,
)


def check_length_definitions():
    """Check if matrix counts edges while DFS counts nodes."""

    # Simple test graph
    simple_graph = {"A": ["B"], "B": ["C"], "C": []}

    print("Testing on simple graph A->B->C")
    print("Path A->B->C has 3 nodes and 2 edges")

    # Test with constraints that should give us the path A->B->C
    constraints = PathConstraints(
        min_length=2, max_length=3, source_node="A", target_node="C"
    )

    # Matrix count
    matrix_result = count_paths_between_nodes(simple_graph, constraints, verbose=True)
    print(f"\nMatrix result: {matrix_result}")

    # DFS generation
    paths = generate_all_paths(simple_graph, constraints)
    print(f"\nDFS found {len(paths)} paths:")
    for path in paths:
        print(f"  Path: {' -> '.join(path)}")
        print(f"  Nodes in path: {len(path)}")
        print(f"  Edges in path: {len(path) - 1}")

    # Now let's check with the actual graph
    print("\n" + "=" * 50)
    print("Checking the actual transaction graph...")

    constraints = PathConstraints(
        min_length=3, max_length=5, source_node="START", target_node="END"
    )

    # Get one example path from DFS
    paths = generate_all_paths(TRANSACTION_GRAPH, constraints)
    if paths:
        example_path = paths[0]
        print(f"\nExample path: {' -> '.join(example_path)}")
        print(f"Number of nodes: {len(example_path)}")
        print(f"Number of edges: {len(example_path) - 1}")

        # Check what the matrix considers as length
        print(f"\nIn PathConstraints, when we say min_length=3, max_length=5:")
        print(f"- Matrix interprets this as: paths with 3-5 edges")
        print(f"- DFS currently uses: paths with 3-5 nodes")
        print(f"- This is why DFS length 3 = Matrix length 2, etc.")


if __name__ == "__main__":
    check_length_definitions()
