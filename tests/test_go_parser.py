"""Unit tests for GoParser — validates regex/line-based heuristics."""

import unittest

from sentinel.parsers.go import GoParser

_PARSER = GoParser()


class TestComputeComplexity(unittest.TestCase):
    def test_simple_code(self):
        complexity, nesting = _PARSER.compute_complexity("x := 1\n")
        self.assertEqual(complexity, 1)
        self.assertEqual(nesting, 0)

    def test_if_statement(self):
        source = """\
if x > 0 {
    doSomething()
}
"""
        complexity, nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 2)
        self.assertEqual(nesting, 1)

    def test_nested_branches(self):
        source = """\
if x > 0 {
    for i := 0; i < 10; i++ {
        if y {
            foo()
        }
    }
}
"""
        complexity, nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 4)
        self.assertEqual(nesting, 3)

    def test_switch_statement(self):
        source = """\
switch x {
case 1:
    fmt.Println("one")
case 2:
    fmt.Println("two")
}
"""
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 4)

    def test_select_statement(self):
        source = """\
select {
case msg := <-ch:
    fmt.Println(msg)
default:
    fmt.Println("nothing")
}
"""
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 3)

    def test_logical_operators(self):
        source = "if a && b || c {\n    foo()\n}\n"
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 4)

    def test_for_loop(self):
        source = """\
for i := 0; i < 10; i++ {
    fmt.Println(i)
}
"""
        complexity, nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 2)
        self.assertEqual(nesting, 1)


class TestFindFunctionLengths(unittest.TestCase):
    def test_simple_function(self):
        source = """\
func hello() {
    x := 1
    y := 2
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "hello")
        self.assertEqual(funcs[0].line, 1)

    def test_function_with_params(self):
        source = """\
func add(a, b int) int {
    return a + b
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].params, 2)

    def test_method_with_receiver(self):
        source = """\
func (s *Server) Start(addr string) error {
    fmt.Println(addr)
    return nil
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "Start")

    def test_multiple_functions(self):
        source = """\
func foo() {
    fmt.Println("foo")
}

func bar() {
    fmt.Println("bar")
    fmt.Println("bar")
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 2)
        self.assertEqual(funcs[0].name, "foo")
        self.assertEqual(funcs[1].name, "bar")

    def test_nested_braces(self):
        source = """\
func process() {
    if true {
        for i := 0; i < 10; i++ {
            fmt.Println(i)
        }
    }
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "process")


class TestFindUnusedImports(unittest.TestCase):
    def test_used_import(self):
        source = """\
package main

import "fmt"

func main() {
    fmt.Println("hello")
}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 0)

    def test_unused_import(self):
        source = """\
package main

import "fmt"

func main() {
    x := 1
    _ = x
}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].name, "fmt")

    def test_group_imports(self):
        source = """\
package main

import (
    "fmt"
    "os"
)

func main() {
    fmt.Println("hello")
}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].name, "os")

    def test_no_imports(self):
        source = """\
package main

func main() {}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 0)


class TestParseImports(unittest.TestCase):
    def test_single_import(self):
        source = 'import "fmt"'
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, ["fmt"])

    def test_group_imports(self):
        source = """\
import (
    "fmt"
    "os"
)
"""
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, ["fmt", "os"])

    def test_no_imports(self):
        source = "package main\n"
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, [])

    def test_dotted_import(self):
        source = 'import "net/http"'
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, ["net/http"])

    def test_deduplication(self):
        source = """\
import "fmt"
import "fmt"
"""
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, ["fmt"])


class TestFindFunctionsWithDocstrings(unittest.TestCase):
    def test_function_with_comment(self):
        source = """\
// Hello does something.
func Hello() {
    fmt.Println("hello")
}
"""
        docs = _PARSER.find_functions_with_docstrings(source)
        self.assertEqual(len(docs), 1)
        self.assertTrue(docs[0].has_docstring)

    def test_function_without_comment(self):
        source = """\
func Hello() {
    fmt.Println("hello")
}
"""
        docs = _PARSER.find_functions_with_docstrings(source)
        self.assertEqual(len(docs), 1)
        self.assertFalse(docs[0].has_docstring)

    def test_method_with_comment(self):
        source = """\
// Start begins the server.
func (s *Server) Start() {
    fmt.Println("starting")
}
"""
        docs = _PARSER.find_functions_with_docstrings(source)
        self.assertEqual(len(docs), 1)
        self.assertTrue(docs[0].has_docstring)


class TestFindTooManyParams(unittest.TestCase):
    def test_within_limit(self):
        source = """\
func add(a, b int) int {
    return a + b
}
"""
        results = _PARSER.find_too_many_params(source, max_params=5)
        self.assertEqual(len(results), 0)

    def test_exceeds_limit(self):
        source = """\
func process(a, b, c, d, e, f int) {
    fmt.Println(a, b, c, d, e, f)
}
"""
        results = _PARSER.find_too_many_params(source, max_params=3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "process")
        self.assertEqual(results[0].params, 6)


class TestFindNamingViolations(unittest.TestCase):
    def test_valid_names(self):
        source = """\
func Hello() {}
func world() {}
type Server struct{}
"""
        violations = _PARSER.find_naming_violations(source)
        self.assertEqual(len(violations), 0)

    def test_lowercase_exported(self):
        source = "func hello() {}\n"
        violations = _PARSER.find_naming_violations(source)
        self.assertEqual(len(violations), 0)

    def test_invalid_type_name(self):
        source = "type my_struct struct{}\n"
        violations = _PARSER.find_naming_violations(source)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].kind, "type")


class TestFindShadowedBuiltins(unittest.TestCase):
    def test_shadow_len(self):
        source = "len := 10\n"
        results = _PARSER.find_shadowed_builtins(source)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "len")

    def test_no_shadow(self):
        source = "x := 10\n"
        results = _PARSER.find_shadowed_builtins(source)
        self.assertEqual(len(results), 0)


class TestModuleHasDocstring(unittest.TestCase):
    def test_package_comment(self):
        self.assertTrue(_PARSER.find_module_has_docstring("// Package main\n"))

    def test_block_comment(self):
        self.assertTrue(_PARSER.find_module_has_docstring("/* Package main */\n"))

    def test_no_comment(self):
        self.assertFalse(_PARSER.find_module_has_docstring("package main\n"))


class TestImmutableGoDefaults(unittest.TestCase):
    def test_always_empty(self):
        self.assertEqual(_PARSER.find_mutable_defaults("func f(x int) {}"), [])

    def test_always_empty_type_hints(self):
        self.assertEqual(_PARSER.find_missing_type_hints("func f() {}"), [])

    def test_always_empty_undocumented_params(self):
        self.assertEqual(_PARSER.find_undocumented_params("func f(x int) {}"), [])

    def test_always_empty_inconsistent_returns(self):
        self.assertEqual(_PARSER.find_inconsistent_returns("func f() { return 1 }"), [])

    def test_always_empty_unnecessary_else(self):
        self.assertEqual(_PARSER.find_unnecessary_else("if true {} else {}"), [])


if __name__ == "__main__":
    unittest.main()
