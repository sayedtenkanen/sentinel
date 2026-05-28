"""Tests for context hub (ADLC Deploy phase)."""

import os
import tempfile
import unittest

from sentinel.govern.context_hub import ContextHub, Profile, ProfileEntry


class TestContextHub(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.hub = ContextHub(base_dir=self.tmpdir)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_list_profiles_empty(self):
        self.assertEqual(self.hub.list_profiles(), [])

    def test_create_and_get_profile(self):
        profile = self.hub.create_profile("default")
        self.assertEqual(profile.name, "default")
        self.assertEqual(len(profile.entries), 0)

        loaded = self.hub.get_profile("default")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "default")

    def test_create_profile_duplicate(self):
        self.hub.create_profile("test")
        with self.assertRaises(FileExistsError):
            self.hub.create_profile("test")

    def test_set_and_get_entry(self):
        self.hub.create_profile("dev")
        entry = self.hub.set_entry("dev", "complexity_threshold", 30, "Max cyclomatic complexity")
        self.assertEqual(entry.key, "complexity_threshold")
        self.assertEqual(entry.value, 30)
        self.assertIn(entry.description, "Max cyclomatic complexity")

        retrieved = self.hub.get_entry("dev", "complexity_threshold")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.value, 30)

    def test_get_entry_nonexistent(self):
        self.hub.create_profile("dev")
        entry = self.hub.get_entry("dev", "nonexistent")
        self.assertIsNone(entry)

    def test_delete_entry(self):
        self.hub.create_profile("dev")
        self.hub.set_entry("dev", "key1", "val1")
        self.assertTrue(self.hub.delete_entry("dev", "key1"))
        self.assertIsNone(self.hub.get_entry("dev", "key1"))

    def test_delete_nonexistent_entry(self):
        self.hub.create_profile("dev")
        self.assertFalse(self.hub.delete_entry("dev", "nonexistent"))

    def test_delete_profile(self):
        self.hub.create_profile("temp")
        self.assertTrue(self.hub.delete_profile("temp"))
        self.assertIsNone(self.hub.get_profile("temp"))

    def test_delete_nonexistent_profile(self):
        self.assertFalse(self.hub.delete_profile("nonexistent"))

    def test_list_profiles(self):
        self.hub.create_profile("dev")
        self.hub.create_profile("prod")
        self.hub.create_profile("staging")
        profiles = self.hub.list_profiles()
        self.assertEqual(len(profiles), 3)
        self.assertIn("dev", profiles)

    def test_version_tracking(self):
        self.hub.create_profile("test")
        e1 = self.hub.set_entry("test", "key", "value1")
        self.assertTrue(len(e1.version) > 0)
        e2 = self.hub.set_entry("test", "key", "value2")
        self.assertNotEqual(e1.version, e2.version)

    def test_profile_to_dict(self):
        profile = Profile(name="test")
        entry = ProfileEntry(key="k", value=42, version="abc", updated_at="now")
        profile.entries["k"] = entry
        d = profile.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertIn("k", d["entries"])

    def test_profile_from_dict(self):
        data = {
            "name": "migrated",
            "created_at": "2024-01-01",
            "updated_at": "2024-06-01",
            "entries": {
                "threshold": {
                    "value": 25,
                    "version": "abc123",
                    "updated_at": "2024-06-01",
                    "description": "Complexity threshold",
                }
            },
        }
        profile = Profile.from_dict(data)
        self.assertEqual(profile.name, "migrated")
        self.assertEqual(profile.entries["threshold"].value, 25)

    def test_persistence(self):
        self.hub.create_profile("persist")
        self.hub.set_entry("persist", "setting", True)

        hub2 = ContextHub(base_dir=self.tmpdir)
        profile = hub2.get_profile("persist")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.entries["setting"].value, True)

    def test_create_profile_with_entries(self):
        entries = {"max_line_length": 100, "debug": False}
        profile = self.hub.create_profile("with-entries", entries)
        self.assertEqual(len(profile.entries), 2)
        self.assertEqual(profile.entries["max_line_length"].value, 100)

    def test_update_entry_updates_timestamp(self):
        self.hub.create_profile("timestamps")
        e1 = self.hub.set_entry("timestamps", "k", "v1")
        ts1 = e1.updated_at
        e2 = self.hub.set_entry("timestamps", "k", "v2")
        ts2 = e2.updated_at
        self.assertNotEqual(ts1, ts2)


class TestProfile(unittest.TestCase):
    def test_default_timestamps(self):
        p = Profile(name="test")
        self.assertIsNotNone(p.created_at)
        self.assertIsNotNone(p.updated_at)

    def test_empty_entries(self):
        p = Profile(name="empty")
        self.assertEqual(len(p.entries), 0)


if __name__ == "__main__":
    unittest.main()
