"""
Configuration loader for code review bot.

Looks for `.code-review.json` in the project root (or nearest ancestor).
Supports exclusions, per-agent thresholds, and output preferences.

Example `.code-review.json`:
{
    "exclude": ["tests/", "**/fixtures/", "_assets/"],
    "agents": {
        "static-analysis": {
            "complexity_threshold": 20,
            "max_line_length": 120
        }
    },
    "output": {
        "format": "markdown",
        "verbose": false
    }
}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "exclude": [],
    "agents": {},
    "output": {},
}


def find_config(start_dir: str | None = None) -> str | None:
    dirs = [start_dir] if start_dir else []
    if not dirs:
        dirs = [os.getcwd()]
    current = Path(dirs[0]).resolve()
    for parent in [current, *list(current.parents)]:
        candidate = parent / ".code-review.json"
        if candidate.is_file():
            return str(candidate)
    return None


def load_config(path: str | None = None) -> dict[str, Any]:
    if path is None:
        path = find_config()
    if path is None:
        return dict(DEFAULT_CONFIG)
    try:
        with open(path) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)


def matches_exclude(filepath: str, patterns: list[str]) -> bool:
    from fnmatch import fnmatch

    for pattern in patterns:
        if fnmatch(filepath, pattern):
            return True
        if pattern.endswith("/") and pattern.rstrip("/") in filepath:
            return True
        if pattern in filepath:
            return True
    return False


def filter_files(files: list[tuple[str, str]], config: dict[str, Any]) -> list[tuple[str, str]]:
    patterns = config.get("exclude", [])
    if not patterns:
        return files
    return [(p, c) for p, c in files if not matches_exclude(p, patterns)]


def agent_config(config: dict[str, Any], agent_name: str) -> dict[str, Any]:
    return config.get("agents", {}).get(agent_name, {})


def matches_suppress(finding: Any, suppress_rule: dict) -> bool:
    from fnmatch import fnmatch

    rule_match = suppress_rule.get("rule", "*")
    pattern = suppress_rule.get("pattern", "*")

    finding_rule = finding.rule_id if not isinstance(finding, dict) else finding.get("rule_id", "")
    finding_file = finding.file if not isinstance(finding, dict) else finding.get("file", "")

    if rule_match != "*" and not fnmatch(finding_rule, rule_match):
        return False
    return pattern == "*" or fnmatch(finding_file, pattern)


def suppress_findings(findings: list[Any], config: dict[str, Any]) -> list[Any]:
    suppress_rules = config.get("suppress", [])
    if not suppress_rules:
        return findings
    return [f for f in findings if not any(matches_suppress(f, rule) for rule in suppress_rules)]
