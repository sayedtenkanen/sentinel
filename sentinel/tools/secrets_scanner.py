"""
Standalone secrets scanner — detects hardcoded secrets in files.

Designed as a pre-commit check and CI gate. Zero dependencies.
Usage:
    python -m sentinel.tools.secrets_scanner path/to/file.py
    python -m sentinel.tools.secrets_scanner --recursive path/to/dir/
    python -m sentinel.tools.secrets_scanner --exit-zero (warn only)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

SECRET_PATTERNS: list[tuple[str, str]] = [
    # Generic secrets
    ("PASSWORD", r"(?i)password\s*[=:]\s*['\"][^'\"]{4,}['\"]"),
    ("API_KEY", r"(?i)(api[_-]?key|apikey|api_secret)\s*[=:]\s*['\"][^'\"]{4,}['\"]"),
    ("SECRET", "(?i)(secret|token|auth_token|access_token)\\s*[=:]\\s*['\"][^'\"]{4,}['\"]"),
    # Cloud credentials
    ("AWS_KEY", r"(?i)(?:AKIA|ASIA)[A-Z0-9]{16}"),
    ("AWS_SECRET", r"(?i)AWS[_\-]SECRET[_\-]ACCESS[_\-]KEY\s*[=:]\s*['\"][^'\"]+['\"]"),
    ("GCP_KEY", r"(?i)AIza[0-9A-Za-z\-_]{35}"),
    ("AZURE_KEY", "(?i)AccountKey\\s*[=:]\\s*['\"][^'\"]+['\"]"),
    # Tokens
    ("JWT", r"(?i)eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
    ("GITHUB_TOKEN", r"(?i)(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}"),
    ("SLACK_TOKEN", r"(?i)xox[bpras]-\d+-\d+-\d+-[a-f0-9]+"),
    ("STRIPE_LIVE", r"(?i)sk_live_[A-Za-z0-9]+"),
    ("STRIPE_TEST", r"(?i)sk_test_[A-Za-z0-9]+"),
    ("JWT_IN_COMMENT", r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
    # Connection strings
    ("CONN_STRING", r"(?i)(postgres|mysql|mongodb|redis|amqp)://[^:]+:[^@]+@"),
    ("PG_CONN", r"(?i)postgresql://\w+:\w+@"),
    # Private keys
    ("PRIVATE_KEY", r"-----BEGIN\s+(RSA|DSA|EC|OPENSSH|PGP)\s+PRIVATE\s+(KEY|BLOCK)-----"),
]

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".tox",
    "build",
    "dist",
}
EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".so", ".o", ".a", ".lib", ".dll", ".dylib", ".exe", ".bin"}
ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".go",
    ".rs",
    ".rb",
    ".java",
    ".sh",
    ".bash",
    ".zsh",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".cfg",
    ".ini",
    ".env",
    ".txt",
    ".md",
    ".rst",
    ".sql",
    ".tf",
    ".cs",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".vue",
    ".svelte",
}


class SecretFinding:
    def __init__(self, secret_type: str, file: str, line: int, snippet: str) -> None:
        self.secret_type = secret_type
        self.file = file
        self.line = line
        self.snippet = snippet

    def __str__(self) -> str:
        return f"[{self.secret_type:15s}] {self.file}:{self.line}  {self.snippet[:60]}"

    def __repr__(self) -> str:
        return self.__str__()


def scan_file(path: str, content: str | None = None) -> list[SecretFinding]:
    if content is None:
        try:
            with open(path, errors="ignore") as f:
                content = f.read()
        except Exception:
            return []

    findings: list[SecretFinding] = []
    lines = content.split("\n")

    for secret_type, pattern in SECRET_PATTERNS:
        for match in re.finditer(pattern, content):
            line_num = content[: match.start()].count("\n") + 1
            line_text = lines[line_num - 1].strip() if line_num <= len(lines) else ""
            snippet = line_text[:80]
            findings.append(SecretFinding(secret_type, path, line_num, snippet))

    return findings


def scan_path(path: str, recursive: bool = False) -> list[SecretFinding]:
    p = Path(path)
    findings: list[SecretFinding] = []

    if p.is_file():
        ext = p.suffix.lower()
        if ext in ALLOWED_EXTENSIONS:
            findings.extend(scan_file(str(p)))
        return findings

    if p.is_dir() and recursive:
        for root, dirs, files in os.walk(str(p)):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    filepath = os.path.join(root, f)
                    findings.extend(scan_file(filepath))

    return findings


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Secrets scanner — detect hardcoded secrets before commit"
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to scan")
    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Scan directories recursively"
    )
    parser.add_argument(
        "--exit-zero", action="store_true", help="Always exit with code 0 (warnings only)"
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    all_findings: list[SecretFinding] = []
    for path in args.paths:
        all_findings.extend(scan_path(path, recursive=args.recursive))

    if args.format == "json":
        import json

        output = json.dumps(
            [
                {"type": f.secret_type, "file": f.file, "line": f.line, "snippet": f.snippet}
                for f in all_findings
            ],
            indent=2,
        )
        print(output)
    else:
        if not all_findings:
            print("✅ No secrets detected.")
            return 0

        print(f"🔴 Found {len(all_findings)} potential secret(s):\n")
        for finding in sorted(all_findings, key=lambda f: (f.file, f.line)):
            print(f"  {finding}")
        print()

    if args.exit_zero:
        return 0
    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())
