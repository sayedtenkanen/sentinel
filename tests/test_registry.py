"""Tests for agent registry (ADLC Govern phase)."""

import unittest

from sentinel.govern.registry import AgentInfo, AgentRegistry


class TestAgentInfo(unittest.TestCase):
    def test_defaults(self):
        info = AgentInfo(name="test", description="Test agent")
        self.assertEqual(info.version, "1.0.0")
        self.assertEqual(len(info.config_schema), 0)
        self.assertEqual(len(info.capabilities), 0)
        self.assertEqual(len(info.tags), 0)

    def test_to_dict(self):
        info = AgentInfo(
            name="my-agent",
            description="Does stuff",
            version="2.0.0",
            capabilities=["foo"],
            tags=["bar"],
        )
        d = info.to_dict()
        self.assertEqual(d["name"], "my-agent")
        self.assertEqual(d["version"], "2.0.0")
        self.assertIn("foo", d["capabilities"])


class TestAgentRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry()

    def test_empty_registry(self):
        self.assertEqual(len(self.registry.list_agents()), 0)

    def test_register_and_get(self):
        info = AgentInfo(name="test-agent", description="A test agent")
        self.registry.register(info)
        retrieved = self.registry.get("test-agent")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "test-agent")

    def test_unregister(self):
        self.registry.register(AgentInfo(name="temp", description="Temporary"))
        self.assertTrue(self.registry.unregister("temp"))
        self.assertIsNone(self.registry.get("temp"))

    def test_unregister_nonexistent(self):
        self.assertFalse(self.registry.unregister("nonexistent"))

    def test_list_empty(self):
        self.assertEqual(len(self.registry.list_agents()), 0)

    def test_list_multiple(self):
        self.registry.register(AgentInfo(name="b", description="Second"))
        self.registry.register(AgentInfo(name="a", description="First"))
        names = [a.name for a in self.registry.list_agents()]
        self.assertEqual(names, ["a", "b"])

    def test_find_by_tag(self):
        a1 = AgentInfo(name="agent1", description="", tags=["core", "security"])
        a2 = AgentInfo(name="agent2", description="", tags=["core"])
        self.registry.register(a1)
        self.registry.register(a2)
        results = self.registry.find_by_tag("security")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "agent1")

    def test_find_by_capability(self):
        a1 = AgentInfo(name="a1", description="", capabilities=["linting"])
        a2 = AgentInfo(name="a2", description="", capabilities=["security"])
        self.registry.register(a1)
        self.registry.register(a2)
        results = self.registry.find_by_capability("security")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "a2")

    def test_to_dict(self):
        self.registry.register(AgentInfo(name="x", description="Agent X"))
        d = self.registry.to_dict()
        self.assertIn("agents", d)
        self.assertEqual(len(d["agents"]), 1)

    def test_default_registry(self):
        registry = AgentRegistry.default()
        self.assertEqual(len(registry.list_agents()), 6)
        self.assertIsNotNone(registry.get("static-analysis"))
        self.assertIsNotNone(registry.get("security"))
        self.assertIsNotNone(registry.get("style"))
        self.assertIsNotNone(registry.get("best-practices"))
        self.assertIsNotNone(registry.get("documentation"))
        self.assertIsNotNone(registry.get("summary"))

    def test_agent_find_multiple_tags(self):
        a = AgentInfo(name="multi", description="", tags=["core", "docs", "security"])
        self.registry.register(a)
        self.assertEqual(len(self.registry.find_by_tag("core")), 1)
        self.assertEqual(len(self.registry.find_by_tag("docs")), 1)
        self.assertEqual(len(self.registry.find_by_tag("security")), 1)


if __name__ == "__main__":
    unittest.main()
