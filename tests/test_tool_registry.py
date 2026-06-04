"""Unit tests for the tool registry."""

import unittest

from sentinel.tools.tool_registry import Tool, ToolRegistry, default_registry


class TestTool(unittest.TestCase):
    def test_tool_creation(self):
        tool = Tool(
            name="test_tool",
            description="A test tool",
            fn=lambda x: x,
            parameters=[],
            returns="str",
        )
        self.assertEqual(tool.name, "test_tool")
        self.assertEqual(tool.description, "A test tool")

    def test_tool_ordering(self):
        t1 = Tool(name="b", description="second", fn=lambda: None)
        t2 = Tool(name="a", description="first", fn=lambda: None)
        self.assertEqual(sorted([t1, t2], key=lambda t: t.name), [t2, t1])


class TestToolRegistryBasics(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def test_register_and_get(self):
        def my_tool(x: int) -> int:
            return x * 2

        self.registry.register(my_tool)
        tool = self.registry.get("my_tool")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "my_tool")

    def test_register_with_custom_name(self):
        def add(a: int, b: int) -> int:
            return a + b

        self.registry.register(add, name="add_numbers")
        tool = self.registry.get("add_numbers")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "add_numbers")

    def test_register_many(self):
        def double(x: int) -> int:
            return x * 2

        def triple(x: int) -> int:
            return x * 3

        self.registry.register_many(double=double, triple=triple)
        self.assertIsNotNone(self.registry.get("double"))
        self.assertIsNotNone(self.registry.get("triple"))

    def test_get_unknown(self):
        self.assertIsNone(self.registry.get("nonexistent"))

    def test_list_tools_empty(self):
        self.assertEqual(self.registry.list_tools(), [])

    def test_list_tools_sorted(self):
        self.registry.register(lambda: None, name="z_tool")
        self.registry.register(lambda: None, name="a_tool")
        names = [t.name for t in self.registry.list_tools()]
        self.assertEqual(names, ["a_tool", "z_tool"])

    def test_call_tool(self):
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        self.registry.register(greet)
        result = self.registry.call("greet", name="World")
        self.assertEqual(result, "Hello, World!")

    def test_call_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.registry.call("nonexistent")

    def test_call_with_args(self):
        def multiply(a: int, b: int = 2) -> int:
            return a * b

        self.registry.register(multiply)
        self.assertEqual(self.registry.call("multiply", a=5, b=3), 15)
        self.assertEqual(self.registry.call("multiply", a=5), 10)


class TestToolRegistryParameters(unittest.TestCase):
    def test_detects_required_params(self):
        def fn(required: str, optional: int = 42) -> str:
            return required * optional

        registry = ToolRegistry()
        registry.register(fn)
        tool = registry.get("fn")
        self.assertEqual(len(tool.parameters), 2)
        req = [p for p in tool.parameters if p.required]
        opt = [p for p in tool.parameters if not p.required]
        self.assertEqual(len(req), 1)
        self.assertEqual(req[0].name, "required")
        self.assertEqual(len(opt), 1)
        self.assertEqual(opt[0].name, "optional")

    def test_detects_param_types(self):
        def fn(name: str, count: int, debug: bool = False) -> None:
            pass

        registry = ToolRegistry()
        registry.register(fn)
        tool = registry.get("fn")
        types = {p.name: p.type_str for p in tool.parameters}
        self.assertEqual(types["name"], "str")
        self.assertEqual(types["count"], "int")
        self.assertEqual(types["debug"], "bool")

    def test_detects_return_type(self):
        def fn() -> dict:
            return {}

        registry = ToolRegistry()
        registry.register(fn)
        tool = registry.get("fn")
        self.assertEqual(tool.returns, "dict")


class TestToolRegistryHelp(unittest.TestCase):
    def test_help_text_empty(self):
        registry = ToolRegistry()
        help_text = registry.get_help()
        self.assertIn("Available Direct Tools", help_text)

    def test_help_text_includes_tools(self):
        def my_tool(path: str) -> str:
            """Reads a file and returns its contents."""
            return ""

        registry = ToolRegistry()
        registry.register(my_tool)
        help_text = registry.get_help()
        self.assertIn("my_tool", help_text)
        self.assertIn("Reads a file and returns its contents", help_text)

    def test_help_text_includes_params(self):
        def search(query: str, limit: int = 10) -> list:
            return []

        registry = ToolRegistry()
        registry.register(search)
        help_text = registry.get_help()
        self.assertIn("query: str", help_text)
        self.assertIn("limit: int (optional)", help_text)


class TestDefaultRegistry(unittest.TestCase):
    def test_default_registry_has_tools(self):
        registry = default_registry()
        tools = registry.list_tools()
        self.assertGreater(len(tools), 0)

    def test_default_has_compute_complexity(self):
        registry = default_registry()
        tool = registry.get("compute_complexity")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "compute_complexity")

    def test_default_has_find_function_lengths(self):
        registry = default_registry()
        self.assertIsNotNone(registry.get("find_function_lengths"))

    def test_default_has_find_unused_imports(self):
        registry = default_registry()
        self.assertIsNotNone(registry.get("find_unused_imports"))

    def test_default_has_scan_secrets(self):
        registry = default_registry()
        tool = registry.get("scan_secrets")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "scan_secrets")

    def test_default_has_parse_diff(self):
        registry = default_registry()
        self.assertIsNotNone(registry.get("parse_diff"))

    def test_default_has_detect_language(self):
        registry = default_registry()
        self.assertIsNotNone(registry.get("detect_language"))

    def test_default_tools_have_descriptions(self):
        registry = default_registry()
        for tool in registry.list_tools():
            self.assertTrue(len(tool.description) > 0, f"{tool.name} has no description")

    def test_default_tools_have_params_defined(self):
        registry = default_registry()
        for tool in registry.list_tools():
            self.assertIsInstance(tool.parameters, list)
            for param in tool.parameters:
                self.assertTrue(len(param.name) > 0)

    def test_default_call_scan_secrets(self):
        registry = default_registry()
        result = registry.call("scan_secrets", path="test.py", content='password = "secret"')
        self.assertIsInstance(result, list)

    def test_default_call_compute_complexity(self):
        registry = default_registry()
        result = registry.call("compute_complexity", source="def foo():\n    if x:\n        pass\n")
        self.assertIsInstance(result, tuple)

    def test_default_call_detect_language(self):
        registry = default_registry()
        result = registry.call("detect_language", filename="main.py")
        self.assertEqual(result, "python")


class TestDefaultRegistrySingleton(unittest.TestCase):
    def test_singleton(self):
        r1 = default_registry()
        r2 = default_registry()
        self.assertIs(r1, r2)

    def test_registration_updates_singleton(self):
        r1 = default_registry()
        r2 = default_registry()
        def new_tool(): pass
        r1.register(new_tool, name="singleton_test")
        self.assertIsNotNone(r2.get("singleton_test"))


if __name__ == "__main__":
    unittest.main()
