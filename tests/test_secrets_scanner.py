"""Unit tests for the standalone secrets scanner."""

import os
import tempfile
import unittest

from sentinel.tools.secrets_scanner import (
    SecretFinding,
    main,
    scan_file,
    scan_path,
)


class TestSecretsScanner(unittest.TestCase):
    def test_detect_password(self):
        findings = scan_file("test.py", 'password = "supersecret"')
        types = {f.secret_type for f in findings}
        self.assertIn("PASSWORD", types)

    def test_detect_api_key(self):
        findings = scan_file("test.py", 'api_key = "sk-abc123def456"')
        types = {f.secret_type for f in findings}
        self.assertIn("API_KEY", types)

    def test_detect_aws_key(self):
        findings = scan_file(
            "test.py", 'AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
        )
        types = {f.secret_type for f in findings}
        self.assertIn("AWS_SECRET", types)

    def test_detect_jwt(self):
        content = (
            'token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jNqqGk7FUg"'
        )
        findings = scan_file("test.py", content)
        types = {f.secret_type for f in findings}
        self.assertIn("JWT", types)

    def test_detect_private_key_comment(self):
        content = "# -----BEGIN RSA PRIVATE KEY-----\nx = 1\n"
        findings = scan_file("test.py", content)
        types = {f.secret_type for f in findings}
        self.assertIn("PRIVATE_KEY", types)

    def test_detect_connection_string(self):
        content = "postgres://admin:password@localhost:5432/db"
        findings = scan_file("test.py", content)
        types = {f.secret_type for f in findings}
        self.assertIn("CONN_STRING", types)

    def test_detect_github_token(self):
        content = "ghp_abc123def456ghi789jkl012mno345pqr678st"
        findings = scan_file("test.py", content)
        types = {f.secret_type for f in findings}
        self.assertIn("GITHUB_TOKEN", types)

    def test_clean_file_no_findings(self):
        content = """x = 1
y = 2
print(x + y)
"""
        findings = scan_file("test.py", content)
        self.assertEqual(len(findings), 0)

    def test_empty_file(self):
        findings = scan_file("test.py", "")
        self.assertEqual(len(findings), 0)


class TestSecretsScannerFile(unittest.TestCase):
    def test_scan_file_from_disk(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('password = "hunter2"\n')
            path = f.name
        try:
            findings = scan_file(path)
            self.assertGreater(len(findings), 0)
        finally:
            os.unlink(path)

    def test_scan_nonexistent_file(self):
        findings = scan_file("/nonexistent/file.py")
        self.assertEqual(len(findings), 0)

    def test_scan_path_single_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('api_key = "sk-test"\n')
            path = f.name
        try:
            findings = scan_path(path)
            self.assertGreater(len(findings), 0)
        finally:
            os.unlink(path)

    def test_scan_path_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, "a.py")
            with open(f1, "w") as f:
                f.write('password = "secret"\n')
            findings = scan_path(tmpdir, recursive=True)
            self.assertGreater(len(findings), 0)

    def test_excluded_extension(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pyc", delete=False) as f:
            f.write('password = "secret"\n')
            path = f.name
        try:
            findings = scan_path(path)
            self.assertEqual(len(findings), 0)
        finally:
            os.unlink(path)


class TestSecretFinding(unittest.TestCase):
    def test_str_format(self):
        f = SecretFinding("PASSWORD", "test.py", 10, "password = 'secret'")
        output = str(f)
        self.assertIn("PASSWORD", output)
        self.assertIn("test.py:10", output)
        self.assertIn("password", output)


class TestSecretsScannerCLI(unittest.TestCase):
    def test_main_with_clean_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n")
            path = f.name
        try:
            exit_code = main([path])
            self.assertEqual(exit_code, 0)
        finally:
            os.unlink(path)

    def test_main_with_secret_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('password = "secret"\n')
            path = f.name
        try:
            exit_code = main([path])
            self.assertEqual(exit_code, 1)
        finally:
            os.unlink(path)

    def test_main_exit_zero_flag(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('password = "secret"\n')
            path = f.name
        try:
            exit_code = main([path, "--exit-zero"])
            self.assertEqual(exit_code, 0)
        finally:
            os.unlink(path)

    def test_main_json_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('password = "secret"\n')
            path = f.name
        try:
            exit_code = main([path, "--format", "json"])
            self.assertEqual(exit_code, 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
