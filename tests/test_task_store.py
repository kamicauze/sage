"""
Tests for Persistent Task Queue (Phase 3).

Covers:
- SQLite task store CRUD operations
- Task state transitions (QUEUED → RUNNING → COMPLETED/FAILED)
- Observation persistence
- Stale task cleanup
- Stats reporting
- Integration with AgentRegistry
"""

import json
import os
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.agent.task_store import TaskStore


class TestTaskStoreBasic(unittest.TestCase):
    """Test basic CRUD operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_tasks.db")
        self.store = TaskStore(db_path=self.db_path)

    def test_enqueue_creates_task(self):
        task_id = self.store.enqueue("test_agent", "Do something")
        self.assertIsNotNone(task_id)
        self.assertEqual(len(task_id), 8)  # UUID hex[:8]

    def test_get_task_returns_correct_data(self):
        task_id = self.store.enqueue("test_agent", "Test goal", '{"name":"test_agent"}')
        task = self.store.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task["agent_name"], "test_agent")
        self.assertEqual(task["goal"], "Test goal")
        self.assertEqual(task["status"], "QUEUED")

    def test_get_task_not_found(self):
        task = self.store.get_task("nonexistent")
        self.assertIsNone(task)

    def test_get_pending_returns_queued_tasks(self):
        self.store.enqueue("agent1", "Goal 1")
        self.store.enqueue("agent2", "Goal 2")
        pending = self.store.get_pending()
        self.assertEqual(len(pending), 2)

    def test_get_pending_excludes_running(self):
        task_id = self.store.enqueue("agent1", "Goal 1")
        self.store.mark_running(task_id)
        pending = self.store.get_pending()
        self.assertEqual(len(pending), 0)


class TestTaskStateTransitions(unittest.TestCase):
    """Test state transitions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_tasks.db")
        self.store = TaskStore(db_path=self.db_path)

    def test_mark_running(self):
        task_id = self.store.enqueue("agent", "goal")
        self.store.mark_running(task_id)
        task = self.store.get_task(task_id)
        self.assertEqual(task["status"], "RUNNING")
        self.assertIsNotNone(task["started_at"])

    def test_mark_completed(self):
        task_id = self.store.enqueue("agent", "goal")
        self.store.mark_running(task_id)
        self.store.mark_completed(task_id, "Done successfully")
        task = self.store.get_task(task_id)
        self.assertEqual(task["status"], "COMPLETED")
        self.assertEqual(task["result_summary"], "Done successfully")
        self.assertIsNotNone(task["completed_at"])

    def test_mark_failed(self):
        task_id = self.store.enqueue("agent", "goal")
        self.store.mark_running(task_id)
        self.store.mark_failed(task_id, "Something broke")
        task = self.store.get_task(task_id)
        self.assertEqual(task["status"], "FAILED")
        self.assertEqual(task["error"], "Something broke")

    def test_mark_cancelled(self):
        task_id = self.store.enqueue("agent", "goal")
        self.store.mark_cancelled(task_id)
        task = self.store.get_task(task_id)
        self.assertEqual(task["status"], "CANCELLED")


class TestTaskObservations(unittest.TestCase):
    """Test observation persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_tasks.db")
        self.store = TaskStore(db_path=self.db_path)

    def test_add_and_get_observations(self):
        task_id = self.store.enqueue("agent", "goal")
        self.store.add_observation(task_id, "web_search", {"query": "test"}, "Found 5 results")
        self.store.add_observation(task_id, "read_file", {"path": "foo.py"}, "contents...")

        obs = self.store.get_observations(task_id)
        self.assertEqual(len(obs), 2)
        self.assertEqual(obs[0]["tool"], "web_search")
        self.assertEqual(obs[1]["tool"], "read_file")

    def test_observations_ordered_by_timestamp(self):
        task_id = self.store.enqueue("agent", "goal")
        self.store.add_observation(task_id, "tool_a", {}, "first")
        self.store.add_observation(task_id, "tool_b", {}, "second")
        obs = self.store.get_observations(task_id)
        self.assertLessEqual(obs[0]["timestamp"], obs[1]["timestamp"])

    def test_observation_result_truncated(self):
        task_id = self.store.enqueue("agent", "goal")
        long_result = "x" * 10000
        self.store.add_observation(task_id, "tool", {}, long_result)
        obs = self.store.get_observations(task_id)
        self.assertLessEqual(len(obs[0]["result_text"]), 4000)


class TestStaleCleanup(unittest.TestCase):
    """Test stale task cleanup."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_tasks.db")
        self.store = TaskStore(db_path=self.db_path)

    def test_cleanup_stale_marks_as_failed(self):
        task_id = self.store.enqueue("agent", "goal")
        self.store.mark_running(task_id)
        # Manually backdate the started_at to simulate a stale task
        with self.store._connect() as conn:
            conn.execute(
                "UPDATE tasks SET started_at=? WHERE id=?",
                (time.time() - 100 * 3600, task_id),  # 100 hours ago
            )
        cleaned = self.store.cleanup_stale(max_age_hours=72)
        self.assertEqual(cleaned, 1)
        task = self.store.get_task(task_id)
        self.assertEqual(task["status"], "FAILED")
        self.assertIn("Stale", task["error"])

    def test_cleanup_doesnt_touch_recent(self):
        task_id = self.store.enqueue("agent", "goal")
        self.store.mark_running(task_id)
        cleaned = self.store.cleanup_stale(max_age_hours=72)
        self.assertEqual(cleaned, 0)
        task = self.store.get_task(task_id)
        self.assertEqual(task["status"], "RUNNING")


class TestTaskStats(unittest.TestCase):
    """Test stats reporting."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_tasks.db")
        self.store = TaskStore(db_path=self.db_path)

    def test_stats_empty(self):
        stats = self.store.get_stats()
        self.assertEqual(stats, {})

    def test_stats_counts(self):
        t1 = self.store.enqueue("a", "g1")
        t2 = self.store.enqueue("b", "g2")
        t3 = self.store.enqueue("c", "g3")
        self.store.mark_running(t1)
        self.store.mark_completed(t2, "done")
        stats = self.store.get_stats()
        self.assertEqual(stats.get("RUNNING"), 1)
        self.assertEqual(stats.get("COMPLETED"), 1)
        self.assertEqual(stats.get("QUEUED"), 1)

    def test_get_recent_ordered(self):
        self.store.enqueue("a", "first")
        self.store.enqueue("b", "second")
        recent = self.store.get_recent(limit=5)
        self.assertEqual(len(recent), 2)
        # Most recent first
        self.assertEqual(recent[0]["goal"], "second")


class TestRegistryIntegration(unittest.TestCase):
    """Test TaskStore integration with AgentRegistry."""

    def test_registry_has_task_store(self):
        from shared.agent.registry import AgentRegistry
        # Reset singleton
        AgentRegistry._instance = None
        registry = AgentRegistry.get()
        self.assertIsNotNone(registry.task_store)
        self.assertIsInstance(registry.task_store, TaskStore)
        # Clean up singleton
        AgentRegistry._instance = None


if __name__ == "__main__":
    unittest.main()
