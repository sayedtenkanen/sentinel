"""Unit tests for NullParser — validates safe empty defaults."""

import unittest

from sentinel.parsers.null import NullParser

_PARSER = NullParser()


class TestNullParser(unittest.TestCase):
    def test_compute_complexity(self):
        self.assertEqual(_PARSER.compute_complexity(""), (1, 0))

    def test_find_function_lengths(self):
        self.assertEqual(_PARSER.find_function_lengths(""), [])

    def test_find_unused_imports(self):
        self.assertEqual(_PARSER.find_unused_imports(""), [])

    def test_parse_imports(self):
        self.assertEqual(_PARSER.parse_imports(""), [])

    def test_find_functions_with_docstrings(self):
        self.assertEqual(_PARSER.find_functions_with_docstrings(""), [])

    def test_find_mutable_defaults(self):
        self.assertEqual(_PARSER.find_mutable_defaults(""), [])

    def test_find_too_many_params(self):
        self.assertEqual(_PARSER.find_too_many_params("", 5), [])

    def test_find_missing_type_hints(self):
        self.assertEqual(_PARSER.find_missing_type_hints(""), [])

    def test_find_module_has_docstring(self):
        self.assertFalse(_PARSER.find_module_has_docstring(""))

    def test_find_undocumented_params(self):
        self.assertEqual(_PARSER.find_undocumented_params(""), [])

    def test_find_inconsistent_returns(self):
        self.assertEqual(_PARSER.find_inconsistent_returns(""), [])

    def test_find_unnecessary_else(self):
        self.assertEqual(_PARSER.find_unnecessary_else(""), [])

    def test_find_naming_violations(self):
        self.assertEqual(_PARSER.find_naming_violations(""), [])

    def test_find_shadowed_builtins(self):
        self.assertEqual(_PARSER.find_shadowed_builtins(""), [])

    def test_all_methods_return_consistent_types(self):
        complexity = _PARSER.compute_complexity("")
        self.assertIsInstance(complexity, tuple)
        self.assertIsInstance(complexity[0], int)
        self.assertIsInstance(complexity[1], int)
        for method_name, args in (
            ("find_function_lengths", ("",)),
            ("find_unused_imports", ("",)),
            ("parse_imports", ("",)),
            ("find_functions_with_docstrings", ("",)),
            ("find_mutable_defaults", ("",)),
            ("find_too_many_params", ("", 5)),
            ("find_missing_type_hints", ("",)),
            ("find_undocumented_params", ("",)),
            ("find_inconsistent_returns", ("",)),
            ("find_unnecessary_else", ("",)),
            ("find_naming_violations", ("",)),
            ("find_shadowed_builtins", ("",)),
        ):
            result = getattr(_PARSER, method_name)(*args)
            self.assertIsInstance(result, list, f"{method_name} should return list")
        self.assertIsInstance(_PARSER.find_module_has_docstring(""), bool)


if __name__ == "__main__":
    unittest.main()
