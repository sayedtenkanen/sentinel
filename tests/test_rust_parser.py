"""Unit tests for RustParser — validates regex/line-based heuristics."""

import unittest

from sentinel.parsers.rust import RustParser

_PARSER = RustParser()


class TestComputeComplexity(unittest.TestCase):
    def test_simple_code(self):
        complexity, nesting = _PARSER.compute_complexity("let x = 1;\n")
        self.assertEqual(complexity, 1)
        self.assertEqual(nesting, 0)

    def test_if_statement(self):
        source = """\
if x > 0 {
    do_something();
}
"""
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 2)
        self.assertEqual(_nesting, 1)

    def test_nested_branches(self):
        source = """\
if x > 0 {
    for i in 0..10 {
        if y {
            foo();
        }
    }
}
"""
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 4)
        self.assertEqual(_nesting, 3)

    def test_match_statement(self):
        source = """\
match x {
    1 => println!("one"),
    2 => println!("two"),
    _ => println!("other"),
}
"""
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 2)

    def test_loop_statement(self):
        source = """\
loop {
    println!("infinite");
}
"""
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 2)
        self.assertEqual(_nesting, 1)

    def test_logical_operators(self):
        source = "if a && b || c {\n    foo();\n}\n"
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 4)

    def test_while_loop(self):
        source = """\
while x > 0 {
    x -= 1;
}
"""
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 2)
        self.assertEqual(_nesting, 1)

    def test_catch_not_counted(self):
        """Rust has no catch keyword — it should not increase complexity."""
        source = """\
// catch is not Rust syntax
if x > 0 {
    foo();
}
"""
        complexity, _nesting = _PARSER.compute_complexity(source)
        self.assertEqual(complexity, 2)


class TestFindFunctionLengths(unittest.TestCase):
    def test_simple_function(self):
        source = """\
fn hello() {
    let x = 1;
    let y = 2;
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "hello")
        self.assertEqual(funcs[0].line, 1)

    def test_function_with_params(self):
        source = """\
fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].params, 2)

    def test_pub_function(self):
        source = """\
pub fn greet(name: &str) {
    println!("Hello, {}!", name);
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "greet")

    def test_async_function(self):
        source = """\
async fn fetch_data() -> Result<String, Error> {
    Ok("data".to_string())
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "fetch_data")

    def test_multiple_functions(self):
        source = """\
fn foo() {
    println!("foo");
}

fn bar() {
    println!("bar");
    println!("bar");
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 2)
        self.assertEqual(funcs[0].name, "foo")
        self.assertEqual(funcs[1].name, "bar")

    def test_nested_braces(self):
        source = """\
fn process() {
    if true {
        for i in 0..10 {
            println!("{}", i);
        }
    }
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "process")

    def test_method_with_self(self):
        source = """\
impl Server {
    fn start(&self) {
        println!("starting");
    }
}
"""
        funcs = _PARSER.find_function_lengths(source)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "start")
        self.assertEqual(funcs[0].params, 1)


class TestFindUnusedImports(unittest.TestCase):
    def test_used_import(self):
        source = """\
use std::io;

fn main() {
    io::println("hello");
}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 0)

    def test_unused_import(self):
        source = """\
use std::io;

fn main() {
    let x = 1;
    println!("{}", x);
}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].name, "io")

    def test_group_imports(self):
        source = """\
use std::{io, fs};

fn main() {
    io::println("hello");
}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].name, "fs")

    def test_no_imports(self):
        source = """\
fn main() {}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 0)

    def test_nested_path_import(self):
        source = """\
use std::collections::HashMap;

fn main() {
    let map = HashMap::new();
}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 0)

    def test_self_import_not_flagged(self):
        source = """\
use std::io::{self, Write};

fn main() {
    io::println("hello");
}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].name, "Write")

    def test_crate_import_not_flagged(self):
        source = """\
use crate::module;

fn main() {
    module::do_something();
}
"""
        unused = _PARSER.find_unused_imports(source)
        self.assertEqual(len(unused), 0)


class TestParseImports(unittest.TestCase):
    def test_single_import(self):
        source = "use std::io;"
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, ["std::io"])

    def test_group_imports(self):
        source = "use std::{io, fs};"
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, ["fs", "io"])

    def test_no_imports(self):
        source = "fn main() {}\n"
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, [])

    def test_nested_import(self):
        source = "use std::collections::HashMap;"
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, ["std::collections::HashMap"])

    def test_deduplication(self):
        source = """\
use std::io;
use std::io;
"""
        imports = _PARSER.parse_imports(source)
        self.assertEqual(imports, ["std::io"])


class TestFindFunctionsWithDocstrings(unittest.TestCase):
    def test_function_with_doc_comment(self):
        source = """\
/// Hello does something.
fn hello() {
    println!("hello");
}
"""
        docs = _PARSER.find_functions_with_docstrings(source)
        self.assertEqual(len(docs), 1)
        self.assertTrue(docs[0].has_docstring)

    def test_function_without_doc_comment(self):
        source = """\
fn hello() {
    println!("hello");
}
"""
        docs = _PARSER.find_functions_with_docstrings(source)
        self.assertEqual(len(docs), 1)
        self.assertFalse(docs[0].has_docstring)

    def test_function_with_inner_doc(self):
        source = """\
//! Module-level docs

fn init() {
    println!("init");
}
"""
        docs = _PARSER.find_functions_with_docstrings(source)
        self.assertEqual(len(docs), 1)
        self.assertFalse(docs[0].has_docstring)


class TestFindTooManyParams(unittest.TestCase):
    def test_within_limit(self):
        source = """\
fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""
        results = _PARSER.find_too_many_params(source, max_params=5)
        self.assertEqual(len(results), 0)

    def test_exceeds_limit(self):
        source = """\
fn process(a: i32, b: i32, c: i32, d: i32) {
    println!("{} {} {} {}", a, b, c, d);
}
"""
        results = _PARSER.find_too_many_params(source, max_params=3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "process")
        self.assertEqual(results[0].params, 4)

    def test_self_param_not_counted(self):
        source = """\
impl Server {
    fn handle(&self, w: Writer, r: Reader) {
        println!("handling");
    }
}
"""
        results = _PARSER.find_too_many_params(source, max_params=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].params, 2)


class TestFindNamingViolations(unittest.TestCase):
    def test_valid_names(self):
        source = """\
fn hello() {}
struct Server {}
enum Color {}
const MAX_SIZE: u32 = 100;
"""
        violations = _PARSER.find_naming_violations(source)
        self.assertEqual(len(violations), 0)

    def test_camel_case_function(self):
        source = "fn myFunction() {}\n"
        violations = _PARSER.find_naming_violations(source)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].kind, "function")

    def test_snake_case_struct(self):
        source = "struct my_struct {}\n"
        violations = _PARSER.find_naming_violations(source)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].kind, "struct")

    def test_lowercase_enum(self):
        source = "enum color {}\n"
        violations = _PARSER.find_naming_violations(source)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].kind, "enum")

    def test_special_names_not_flagged(self):
        source = """\
fn main() {}
fn new() {}
fn build() {}
fn run() {}
fn test() {}
"""
        violations = _PARSER.find_naming_violations(source)
        self.assertEqual(len(violations), 0)


class TestFindShadowedBuiltins(unittest.TestCase):
    def test_shadow_string(self):
        source = 'let String = "hello";\n'
        results = _PARSER.find_shadowed_builtins(source)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "String")

    def test_no_shadow(self):
        source = "let x = 10;\n"
        results = _PARSER.find_shadowed_builtins(source)
        self.assertEqual(len(results), 0)

    def test_mut_variable(self):
        source = "let mut vec = Vec::new();\n"
        results = _PARSER.find_shadowed_builtins(source)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "vec")


class TestModuleHasDocstring(unittest.TestCase):
    def test_inner_doc_comment(self):
        self.assertTrue(_PARSER.find_module_has_docstring("//! Module docs\n"))

    def test_no_doc_comment(self):
        self.assertFalse(_PARSER.find_module_has_docstring("use std::io;\n"))


class TestImmutableRustDefaults(unittest.TestCase):
    def test_always_empty(self):
        self.assertEqual(_PARSER.find_mutable_defaults("fn f(x: i32) {}"), [])

    def test_always_empty_type_hints(self):
        self.assertEqual(_PARSER.find_missing_type_hints("fn f() {}"), [])

    def test_always_empty_undocumented_params(self):
        self.assertEqual(_PARSER.find_undocumented_params("fn f(x: i32) {}"), [])

    def test_always_empty_inconsistent_returns(self):
        self.assertEqual(_PARSER.find_inconsistent_returns("fn f() -> i32 { 1 }"), [])

    def test_always_empty_unnecessary_else(self):
        self.assertEqual(_PARSER.find_unnecessary_else("if true {} else {}"), [])


if __name__ == "__main__":
    unittest.main()
