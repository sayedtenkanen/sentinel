"""Tests for Sentinel Memory store and models."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sentinel.memory.models import (
    FeedbackEvent,
    Memory,
    MemoryCandidate,
    MemoryType,
    ReviewEvent,
)
from sentinel.memory.store import MemoryStore


class TestMemoryModels(unittest.TestCase):
    def test_memory_defaults(self):
        m = Memory()
        self.assertTrue(m.id.startswith("mem_"))
        self.assertEqual(m.type, MemoryType.CONTEXT)
        self.assertEqual(m.content, {})
        self.assertEqual(m.confidence, 0.0)
        self.assertEqual(m.tags, [])

    def test_memory_type_values(self):
        self.assertEqual(MemoryType.RULE.value, "rule")
        self.assertEqual(MemoryType.PREFERENCE.value, "preference")
        self.assertEqual(MemoryType.CONTEXT.value, "context")
        self.assertEqual(MemoryType.TEMPORAL.value, "temporal")

    def test_memory_candidate(self):
        c = MemoryCandidate(
            type=MemoryType.RULE,
            content={"rule": "SEC001"},
            confidence=0.8,
            evidence=["finding_1", "finding_2"],
        )
        self.assertTrue(c.id.startswith("candidate_"))
        self.assertEqual(c.confidence, 0.8)
        self.assertEqual(len(c.evidence), 2)

    def test_review_event(self):
        e = ReviewEvent(
            file_path="src/main.py",
            finding_id="f1",
            rule_id="SEC001",
            severity="high",
            agent="security",
        )
        self.assertEqual(e.file_path, "src/main.py")
        self.assertEqual(e.severity, "high")

    def test_feedback_event(self):
        f = FeedbackEvent(
            finding_id="f1",
            rating="correct",
            comment="True positive",
        )
        self.assertEqual(f.rating, "correct")
        self.assertIsNone(f.user)


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.store = MemoryStore(self.db_path)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_insert_and_get(self):
        m = Memory(
            id="mem_test",
            type=MemoryType.RULE,
            content={"rule": "SEC001"},
            confidence=0.9,
            tags=["security", "python"],
        )
        self.store.insert(m)

        retrieved = self.store.get("mem_test")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "mem_test")
        self.assertEqual(retrieved.type, MemoryType.RULE)
        self.assertEqual(retrieved.content, {"rule": "SEC001"})
        self.assertAlmostEqual(retrieved.confidence, 0.9)
        self.assertEqual(retrieved.tags, ["security", "python"])

    def test_get_nonexistent(self):
        self.assertIsNone(self.store.get("nonexistent"))

    def test_update(self):
        m = Memory(id="mem_update", confidence=0.5)
        self.store.insert(m)

        result = self.store.update("mem_update", {"confidence": 0.9})
        self.assertTrue(result)

        updated = self.store.get("mem_update")
        self.assertAlmostEqual(updated.confidence, 0.9)

    def test_update_nonexistent(self):
        result = self.store.update("nonexistent", {"confidence": 0.9})
        self.assertFalse(result)

    def test_delete(self):
        m = Memory(id="mem_delete")
        self.store.insert(m)
        self.assertEqual(self.store.count(), 1)

        result = self.store.delete("mem_delete")
        self.assertTrue(result)
        self.assertEqual(self.store.count(), 0)
        self.assertIsNone(self.store.get("mem_delete"))

    def test_delete_nonexistent(self):
        result = self.store.delete("nonexistent")
        self.assertFalse(result)

    def test_list_all(self):
        for i in range(3):
            self.store.insert(Memory(id=f"mem_{i}"))

        all_memories = self.store.list_all()
        self.assertEqual(len(all_memories), 3)

    def test_count(self):
        self.assertEqual(self.store.count(), 0)
        self.store.insert(Memory(id="m1"))
        self.assertEqual(self.store.count(), 1)
        self.store.insert(Memory(id="m2"))
        self.assertEqual(self.store.count(), 2)

    def test_touch(self):
        m = Memory(id="mem_touch")
        self.store.insert(m)

        old_used = m.last_used_at
        result = self.store.touch("mem_touch")
        self.assertTrue(result)

        touched = self.store.get("mem_touch")
        self.assertNotEqual(touched.last_used_at, old_used)

    def test_query_by_type(self):
        self.store.insert(Memory(id="r1", type=MemoryType.RULE))
        self.store.insert(Memory(id="p1", type=MemoryType.PREFERENCE))
        self.store.insert(Memory(id="r2", type=MemoryType.RULE))

        rules = self.store.query(type=MemoryType.RULE)
        self.assertEqual(len(rules), 2)

        prefs = self.store.query(type=MemoryType.PREFERENCE)
        self.assertEqual(len(prefs), 1)

    def test_query_by_confidence(self):
        self.store.insert(Memory(id="low", confidence=0.3))
        self.store.insert(Memory(id="high", confidence=0.9))

        results = self.store.query(min_confidence=0.5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "high")

    def test_query_by_tags(self):
        self.store.insert(Memory(id="m1", tags=["python", "security"]))
        self.store.insert(Memory(id="m2", tags=["javascript"]))
        self.store.insert(Memory(id="m3", tags=["python", "style"]))

        results = self.store.query(tags=["python"])
        self.assertEqual(len(results), 2)

        results = self.store.query(tags=["security"])
        self.assertEqual(len(results), 1)

        results = self.store.query(tags=["python", "security"])
        self.assertEqual(len(results), 1)

    def test_query_exclude_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        self.store.insert(Memory(id="expired", expires_at=past))
        self.store.insert(Memory(id="valid", expires_at=future))
        self.store.insert(Memory(id="no_expiry", expires_at=None))

        results = self.store.query()
        self.assertEqual(len(results), 2)
        ids = [m.id for m in results]
        self.assertIn("valid", ids)
        self.assertIn("no_expiry", ids)
        self.assertNotIn("expired", ids)

    def test_query_include_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.store.insert(Memory(id="expired", expires_at=past))

        results = self.store.query(include_expired=True)
        self.assertEqual(len(results), 1)

    def test_query_combined_filters(self):
        self.store.insert(Memory(id="m1", type=MemoryType.RULE, confidence=0.9, tags=["python"]))
        self.store.insert(Memory(id="m2", type=MemoryType.RULE, confidence=0.3, tags=["python"]))
        self.store.insert(
            Memory(id="m3", type=MemoryType.PREFERENCE, confidence=0.9, tags=["python"])
        )

        results = self.store.query(type=MemoryType.RULE, min_confidence=0.5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "m1")

    def test_insert_replace(self):
        self.store.insert(Memory(id="m1", confidence=0.5))
        self.store.insert(Memory(id="m1", confidence=0.9))

        self.assertEqual(self.store.count(), 1)
        m = self.store.get("m1")
        self.assertAlmostEqual(m.confidence, 0.9)


if __name__ == "__main__":
    unittest.main()
