"""
tests/test_graph.py - Unit tests for the core graph algorithm module.

These tests run with zero infrastructure -- no database, no Redis, no Docker.
Pure Python logic under test.
"""

import pytest

from dag_engine.core.graph import detect_cycles, topological_sort


# ---------------------------------------------------------------------------
# detect_cycles tests
# ---------------------------------------------------------------------------

class TestDetectCycles:

    def test_linear_chain_has_no_cycle(self):
        """A -> B -> C should have no cycle."""
        tasks = [
            {"name": "A", "dependencies": []},
            {"name": "B", "dependencies": ["A"]},
            {"name": "C", "dependencies": ["B"]},
        ]
        assert detect_cycles(tasks) is False

    def test_parallel_tasks_have_no_cycle(self):
        """A and B both feed into C -- no cycle."""
        tasks = [
            {"name": "A", "dependencies": []},
            {"name": "B", "dependencies": []},
            {"name": "C", "dependencies": ["A", "B"]},
        ]
        assert detect_cycles(tasks) is False

    def test_direct_self_dependency_is_cycle(self):
        """A depends on itself -- obvious cycle."""
        tasks = [
            {"name": "A", "dependencies": ["A"]},
        ]
        assert detect_cycles(tasks) is True

    def test_two_node_cycle_detected(self):
        """A -> B -> A forms a cycle."""
        tasks = [
            {"name": "A", "dependencies": ["B"]},
            {"name": "B", "dependencies": ["A"]},
        ]
        assert detect_cycles(tasks) is True

    def test_indirect_cycle_detected(self):
        """A -> B -> C -> A forms a longer cycle."""
        tasks = [
            {"name": "A", "dependencies": ["C"]},
            {"name": "B", "dependencies": ["A"]},
            {"name": "C", "dependencies": ["B"]},
        ]
        assert detect_cycles(tasks) is True

    def test_single_task_no_cycle(self):
        """A single task with no dependencies can't cycle."""
        tasks = [{"name": "A", "dependencies": []}]
        assert detect_cycles(tasks) is False

    def test_empty_task_list(self):
        """Empty graph has no cycles."""
        assert detect_cycles([]) is False


# ---------------------------------------------------------------------------
# topological_sort tests
# ---------------------------------------------------------------------------

class TestTopologicalSort:

    def test_linear_chain_returns_sequential_tiers(self):
        """A -> B -> C should return [['A'], ['B'], ['C']]."""
        tasks = [
            {"name": "A", "dependencies": []},
            {"name": "B", "dependencies": ["A"]},
            {"name": "C", "dependencies": ["B"]},
        ]
        tiers = topological_sort(tasks)
        assert tiers == [["A"], ["B"], ["C"]]

    def test_parallel_tasks_grouped_in_same_tier(self):
        """A and B have no deps -- they should be in the same first tier."""
        tasks = [
            {"name": "A", "dependencies": []},
            {"name": "B", "dependencies": []},
            {"name": "C", "dependencies": ["A", "B"]},
        ]
        tiers = topological_sort(tasks)
        assert len(tiers) == 2
        assert set(tiers[0]) == {"A", "B"}
        assert tiers[1] == ["C"]

    def test_single_task_returns_one_tier(self):
        tasks = [{"name": "A", "dependencies": []}]
        assert topological_sort(tasks) == [["A"]]

    def test_diamond_dependency_pattern(self):
        """
        A -> B -> D
        A -> C -> D
        Expected: [['A'], ['B', 'C'], ['D']]
        """
        tasks = [
            {"name": "A", "dependencies": []},
            {"name": "B", "dependencies": ["A"]},
            {"name": "C", "dependencies": ["A"]},
            {"name": "D", "dependencies": ["B", "C"]},
        ]
        tiers = topological_sort(tasks)
        assert tiers[0] == ["A"]
        assert set(tiers[1]) == {"B", "C"}
        assert tiers[2] == ["D"]

    def test_all_independent_tasks_in_one_tier(self):
        """Four tasks with no dependencies should all be in tier 0."""
        tasks = [
            {"name": "A", "dependencies": []},
            {"name": "B", "dependencies": []},
            {"name": "C", "dependencies": []},
            {"name": "D", "dependencies": []},
        ]
        tiers = topological_sort(tasks)
        assert len(tiers) == 1
        assert set(tiers[0]) == {"A", "B", "C", "D"}
