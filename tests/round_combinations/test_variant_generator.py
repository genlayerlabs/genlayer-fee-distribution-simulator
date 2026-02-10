"""
Tests for the variant generator module.

Verifies that rotation/idle variant expansion works correctly for all
node types in the TRANSACTION_GRAPH.
"""

import pytest
from src.fee_simulator.specification.state_machine.path_analysis.variant_generator import (
    VariantConfig,
    get_normal_round_nodes,
    generate_variants,
    count_variants,
    generate_all_path_variants,
    count_all_path_variants,
)
from src.fee_simulator.specification.state_machine.graph import (
    TRANSACTION_GRAPH,
    GRAPH_NODE_METADATA,
)


class TestGetNormalRoundNodes:
    """Tests for extracting normal round nodes from paths."""

    def test_simple_path_one_normal(self):
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        result = get_normal_round_nodes(path)
        assert result == [(0, "LEADER_RECEIPT_MAJORITY_AGREE")]

    def test_path_with_appeal(self):
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_DISAGREE",
            "END",
        ]
        result = get_normal_round_nodes(path)
        assert result == [
            (0, "LEADER_RECEIPT_MAJORITY_AGREE"),
            (1, "LEADER_RECEIPT_MAJORITY_DISAGREE"),
        ]

    def test_leader_timeout_is_normal(self):
        path = ["START", "LEADER_TIMEOUT", "END"]
        result = get_normal_round_nodes(path)
        assert result == [(0, "LEADER_TIMEOUT")]

    def test_appeal_only_path(self):
        """Appeals between two normals - both normals counted."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_TIMEOUT",
            "END",
        ]
        result = get_normal_round_nodes(path)
        assert result == [
            (0, "LEADER_RECEIPT_MAJORITY_AGREE"),
            (1, "LEADER_TIMEOUT"),
        ]


class TestCountVariants:
    """Tests for counting variants without generating them."""

    def test_leader_timeout_no_idle(self):
        """LEADER_TIMEOUT supports rotations but NOT idle."""
        path = ["START", "LEADER_TIMEOUT", "END"]
        # With max_rotations=2: rotations in {0,1,2} = 3 options, idle always 0 = 1 option
        count = count_variants(path, max_rotations=2, max_idle=2)
        assert count == 3

    def test_leader_receipt_agree_rotations_and_idle(self):
        """LEADER_RECEIPT_MAJORITY_AGREE supports both rotations and idle."""
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        # max_rotations=2: {0,1,2} = 3 options
        # max_idle=2: {0,1,2} = 3 options
        # Total: 3 * 3 = 9
        count = count_variants(path, max_rotations=2, max_idle=2)
        assert count == 9

    def test_appeal_nodes_no_expansion(self):
        """Appeal nodes produce no variants - only the normals do."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_DISAGREE",
            "END",
        ]
        # Two normal rounds, each with 3*3=9 combos → 9*9=81
        count = count_variants(path, max_rotations=2, max_idle=2)
        assert count == 81

    def test_base_case_no_expansion(self):
        """max_rotations=0, max_idle=0 should yield exactly 1 variant."""
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        count = count_variants(path, max_rotations=0, max_idle=0)
        assert count == 1

    def test_two_normal_rounds_multiplicative(self):
        """Two normal rounds → multiplicative count."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_TIMEOUT",
            "END",
        ]
        # First normal: 3 rotations * 3 idle = 9
        # Second normal (LEADER_TIMEOUT): 3 rotations * 1 idle = 3
        # Total: 9 * 3 = 27
        count = count_variants(path, max_rotations=2, max_idle=2)
        assert count == 27

    def test_mixed_node_types(self):
        """Mix of LEADER_RECEIPT and LEADER_TIMEOUT nodes."""
        path = [
            "START",
            "LEADER_RECEIPT_UNDETERMINED",
            "LEADER_APPEAL_SUCCESSFUL",
            "LEADER_TIMEOUT",
            "END",
        ]
        # UNDETERMINED: rot{0,1} * idle{0,1} = 4
        # LEADER_TIMEOUT: rot{0,1} * idle{0} = 2
        # Total: 4 * 2 = 8
        count = count_variants(path, max_rotations=1, max_idle=1)
        assert count == 8


class TestGenerateVariants:
    """Tests for actual variant generation."""

    def test_base_variant_always_present(self):
        """The base variant (0 rotations, 0 idle) should always be first."""
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        variants = list(generate_variants(path, max_rotations=2, max_idle=2))
        base = variants[0]
        assert base.path == path
        assert base.rotation_counts == {}
        assert base.idle_config == {}

    def test_variant_count_matches(self):
        """Number of generated variants should match count_variants."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_TIMEOUT",
            "END",
        ]
        expected = count_variants(path, max_rotations=2, max_idle=1)
        actual = len(list(generate_variants(path, max_rotations=2, max_idle=1)))
        assert actual == expected

    def test_variant_ids_unique(self):
        """All variant IDs should be unique within a path."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_DISAGREE",
            "END",
        ]
        variants = list(generate_variants(path, max_rotations=2, max_idle=2))
        ids = [v.variant_id for v in variants]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {len(ids)} total, {len(set(ids))} unique"

    def test_leader_timeout_idle_always_zero(self):
        """LEADER_TIMEOUT variants should never have idle validators."""
        path = ["START", "LEADER_TIMEOUT", "END"]
        variants = list(generate_variants(path, max_rotations=2, max_idle=2))
        for v in variants:
            assert v.idle_config == {}, f"LEADER_TIMEOUT variant has idle: {v.idle_config}"

    def test_rotation_counts_structure(self):
        """Rotation counts should map normal round index → count."""
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        variants = list(generate_variants(path, max_rotations=2, max_idle=0))
        # Should get: {}, {0: 1}, {0: 2}
        rotation_values = [v.rotation_counts for v in variants]
        assert {} in rotation_values
        assert {0: 1} in rotation_values
        assert {0: 2} in rotation_values

    def test_idle_config_structure(self):
        """Idle config should map normal round index → count."""
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        variants = list(generate_variants(path, max_rotations=0, max_idle=2))
        idle_values = [v.idle_config for v in variants]
        assert {} in idle_values
        assert {0: 1} in idle_values
        assert {0: 2} in idle_values

    def test_all_combinations_present(self):
        """Verify all combinations are generated for a simple case."""
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        variants = list(generate_variants(path, max_rotations=1, max_idle=1))
        # Should get 2*2 = 4 combinations:
        # (rot=0, idle=0), (rot=0, idle=1), (rot=1, idle=0), (rot=1, idle=1)
        assert len(variants) == 4

        combos = [(v.rotation_counts, v.idle_config) for v in variants]
        assert ({}, {}) in combos
        assert ({}, {0: 1}) in combos
        assert ({0: 1}, {}) in combos
        assert ({0: 1}, {0: 1}) in combos


class TestGenerateAllPathVariants:
    """Tests for batch variant generation across multiple paths."""

    def test_batch_count_matches(self):
        paths = [
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
            ["START", "LEADER_TIMEOUT", "END"],
        ]
        expected = count_all_path_variants(paths, max_rotations=1, max_idle=1)
        actual = len(list(generate_all_path_variants(paths, max_rotations=1, max_idle=1)))
        assert actual == expected

    def test_lazy_generation(self):
        """Verify the generator is lazy (doesn't compute all at once)."""
        paths = [
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
            ["START", "LEADER_TIMEOUT", "END"],
        ]
        gen = generate_all_path_variants(paths, max_rotations=1, max_idle=1)
        first = next(gen)
        assert isinstance(first, VariantConfig)


class TestGraphNodeMetadataCompleteness:
    """Verify all relevant TRANSACTION_GRAPH nodes have metadata entries."""

    def test_all_normal_round_nodes_have_metadata(self):
        """Every non-appeal, non-terminal node should have metadata."""
        from src.fee_simulator.core.path_to_transaction import is_appeal_node

        for node in TRANSACTION_GRAPH:
            if node in ("START", "END"):
                continue
            if is_appeal_node(node):
                continue
            assert node in GRAPH_NODE_METADATA, (
                f"Normal round node '{node}' missing from GRAPH_NODE_METADATA"
            )

    def test_appeal_nodes_not_in_metadata(self):
        """Appeal nodes should NOT be in the metadata (they don't expand)."""
        from src.fee_simulator.core.path_to_transaction import is_appeal_node

        for node in TRANSACTION_GRAPH:
            if is_appeal_node(node):
                assert node not in GRAPH_NODE_METADATA, (
                    f"Appeal node '{node}' should not be in GRAPH_NODE_METADATA"
                )

    def test_metadata_has_required_keys(self):
        """Each metadata entry should have 'rotations' and 'idle' keys."""
        for node, meta in GRAPH_NODE_METADATA.items():
            assert "rotations" in meta, f"Node '{node}' missing 'rotations' key"
            assert "idle" in meta, f"Node '{node}' missing 'idle' key"
            assert isinstance(meta["rotations"], bool)
            assert isinstance(meta["idle"], bool)


class TestVariantConfigProperties:
    """Tests for VariantConfig data structure."""

    def test_named_tuple_unpacking(self):
        vc = VariantConfig(
            path=["START", "LEADER_TIMEOUT", "END"],
            rotation_counts={0: 1},
            idle_config={},
        )
        path, rot, idle = vc
        assert path == ["START", "LEADER_TIMEOUT", "END"]
        assert rot == {0: 1}
        assert idle == {}

    def test_variant_id_deterministic(self):
        """Same inputs should always produce the same variant_id."""
        vc1 = VariantConfig(
            path=["START", "LEADER_TIMEOUT", "END"],
            rotation_counts={0: 1},
            idle_config={},
        )
        vc2 = VariantConfig(
            path=["START", "LEADER_TIMEOUT", "END"],
            rotation_counts={0: 1},
            idle_config={},
        )
        assert vc1.variant_id == vc2.variant_id

    def test_different_variants_different_ids(self):
        vc1 = VariantConfig(
            path=["START", "LEADER_TIMEOUT", "END"],
            rotation_counts={0: 1},
            idle_config={},
        )
        vc2 = VariantConfig(
            path=["START", "LEADER_TIMEOUT", "END"],
            rotation_counts={0: 2},
            idle_config={},
        )
        assert vc1.variant_id != vc2.variant_id
