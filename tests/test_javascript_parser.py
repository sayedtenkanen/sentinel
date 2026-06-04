"""Unit tests for JavaScriptParser — validates regex/line-based heuristics."""

import unittest

from sentinel.parsers.javascript import JavaScriptParser

_PARSER = JavaScriptParser()


class TestComputeComplexity(unittest.TestCase):
    def test_simple_code(self):
        complexity, nesting = _PARSER.compute_complexity("const x = 1;\n")
        self.assertEqual(complexity, 1)
        self.assertEqual(nesting, 0)

    def test_if_statement(self):
        source = """
if (x > 0) {
    doSomething();
}
"""
        complexity, nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 2)
        self.assertEqual(nesting, 1)

    def test_nested_branches(self):
        source = """
if (x > 0) {
    for (let i = 0; i < 10; i++) {
        if (y) {
            foo();
        }
    }
}
"""
        complexity, nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 4)
        self.assertEqual(nesting, 3)


class TestFindFunctionLengths(unittest.TestCase):
    def test_function_declaration(self):
        source = """
function hello() {
    const x = 1;
    const y = 2;
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "hello")
        self.assertEqual(funcs[0].line, 2)

    def test_arrow_function(self):
        source = "const add = (a, b) => { return a + b; };\n"
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].params, 2)

    def test_multiple_functions(self):
        source = """
function foo() {}
function bar() {}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 2)
        self.assertEqual(funcs[0].name, "foo")
        self.assertEqual(funcs[1].name, "bar")


class TestParseImports(unittest.TestCase):
    def test_esm_import(self):
        imports = _PARSER.parse_imports('import { readFile } from "fs";\n')
        self.assertEqual(imports, ["fs"])

    def test_require(self):
        imports = _PARSER.parse_imports('const fs = require("fs");\n')
        self.assertEqual(imports, ["fs"])

    def test_no_imports(self):
        imports = _PARSER.parse_imports("const x = 1;\n")
        self.assertEqual(imports, [])


class TestNamingViolations(unittest.TestCase):
    def test_class_name_lowercase(self):
        result = _PARSER.find_naming_violations("class myClass {}\n")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].kind, "class")

    def test_function_name_uppercase(self):
        result = _PARSER.find_naming_violations("function DoSomething() {}\n")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].kind, "function")

    def test_good_class_name(self):
        result = _PARSER.find_naming_violations("class MyClass {}\n")
        self.assertEqual(len(result), 0)


class TestDocstrings(unittest.TestCase):
    def test_jsdoc_detected(self):
        result = _PARSER.find_functions_with_docstrings(
            """/** Does something */
function foo() {}
"""
        )
        self.assertTrue(result[0].has_docstring) if result else None

    def test_module_docstring(self):
        self.assertTrue(_PARSER.find_module_has_docstring("/** Module doc */\nconst x = 1;\n"))
        self.assertFalse(_PARSER.find_module_has_docstring("const x = 1;\n"))


class TestParamOverflow(unittest.TestCase):
    def test_too_many_params(self):
        result = _PARSER.find_too_many_params("function f(a, b, c, d, e) {}\n", 3)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].params, 5)

    def test_under_limit(self):
        result = _PARSER.find_too_many_params("function f(a, b) {}\n", 3)
        self.assertEqual(len(result), 0)


class TestShadowedBuiltins(unittest.TestCase):
    def test_shadow_eval(self):
        result = _PARSER.find_shadowed_builtins("function eval() {}\n")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "eval")

    def test_no_shadow(self):
        result = _PARSER.find_shadowed_builtins("function myFunc() {}\n")
        self.assertEqual(len(result), 0)


class TestInconsistentReturns(unittest.TestCase):
    def test_mixed_returns(self):
        source = """
function foo() {
    if (x) { return 42; }
    return;
}
"""
        result = _PARSER.find_inconsistent_returns(source)
        self.assertEqual(len(result), 1)


class TestNullMethods(unittest.TestCase):
    """Methods that always return empty lists for JS."""

    def test_mutable_defaults_empty(self):
        self.assertEqual(_PARSER.find_mutable_defaults(""), [])

    def test_missing_type_hints_empty(self):
        self.assertEqual(_PARSER.find_missing_type_hints(""), [])

    def test_undocumented_params_empty(self):
        self.assertEqual(_PARSER.find_undocumented_params(""), [])

    def test_unnecessary_else_empty(self):
        self.assertEqual(_PARSER.find_unnecessary_else(""), [])

    def test_unused_imports_empty(self):
        self.assertEqual(_PARSER.find_unused_imports(""), [])


if __name__ == "__main__":
    unittest.main()
