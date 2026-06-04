"""Offline rule suggestion miner — mines knowledge base findings for new patterns.

Discovers candidate rules by clustering similar findings and extracting
common patterns. Designed for offline analysis (ADLC Govern phase).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def extract_common_pattern(messages: list[str]) -> str | None:
    """Try to find a common regex pattern from a group of similar messages.

    Uses longest common substring heuristics. Returns None if no
    meaningful pattern can be extracted.
    """
    if len(messages) < 2:
        return None

    cleaned = [re.sub(r"['\"][^'\"]*['\"]", "'...'", m) for m in messages]
    tokens_list = [m.split() for m in cleaned]

    common = set(tokens_list[0]) if tokens_list else set()
    for tokens in tokens_list[1:]:
        common &= set(tokens)

    if not common or len(common) < 2:
        return None

    return " ".join(sorted(common, key=lambda t: -len(t)))[:120]


def cluster_findings(findings: list[dict]) -> list[list[dict]]:
    """Group findings by similarity of message text.

    Uses simple prefix matching: findings whose messages share the
    first 40 characters are clustered together.
    """
    clusters: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        msg = f.get("message", "")
        key = msg[:40]
        clusters[key].append(f)
    return list(clusters.values())


class RuleMiner:
    """Mines candidate rules from a KnowledgeBase directory."""

    def __init__(self, kb_dir: str):
        self.kb_dir = Path(kb_dir)

    def load_findings(self) -> list[dict]:
        kb_path = self.kb_dir / "knowledge_base.json"
        if not kb_path.exists():
            return []
        data = json.loads(kb_path.read_text())
        findings: list[dict] = []
        for _chunk_id, chunk_findings in data.get("findings", {}).items():
            for f in chunk_findings:
                findings.append(f)
        return findings

    def mine(self) -> list[dict]:
        findings = self.load_findings()
        if not findings:
            return []

        clusters = cluster_findings(findings)
        rules: list[dict] = []

        for i, cluster in enumerate(clusters):
            if len(cluster) < 2:
                continue

            messages = [f.get("message", "") for f in cluster if f.get("message")]
            pattern = extract_common_pattern(messages)
            if not pattern:
                continue

            severities = Counter(f.get("severity", "info") for f in cluster)
            source_rules = sorted(set(f.get("rule_id", "?") for f in cluster if f.get("rule_id")))
            source_files = sorted(
                set(f.get("_source_file", "") for f in cluster if f.get("_source_file"))
            )

            top_severity = severities.most_common(1)[0][0]
            suggestion = cluster[0].get("suggestion", "")

            rules.append(
                {
                    "suggested_rule_id": f"MINED{i + 1:03d}",
                    "pattern": pattern,
                    "category": _infer_category(source_rules),
                    "message": messages[0][:100],
                    "suggestion": suggestion[:200] if suggestion else "",
                    "frequency": len(cluster),
                    "severity": top_severity,
                    "source_rules": source_rules,
                    "source_files": len(source_files),
                }
            )

        rules.sort(key=lambda r: -r["frequency"])
        return rules

    def export(self, output_path: str | None = None) -> str:
        rules = self.mine()
        result = json.dumps({"mined_rules": rules, "count": len(rules)}, indent=2)
        if output_path:
            Path(output_path).write_text(result)
        return result


def _infer_category(source_rules: list[str]) -> str:
    for sr in source_rules:
        if sr.startswith("SEC"):
            return "security"
        if sr.startswith("STY"):
            return "style"
        if sr.startswith("ST"):
            return "static-analysis"
        if sr.startswith("BP"):
            return "best-practices"
        if sr.startswith("DOC"):
            return "documentation"
    return "general"


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Mine knowledge base for new rule suggestions")
    parser.add_argument("--kb-dir", required=True, help="RAG knowledge base directory")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    args = parser.parse_args(argv)

    miner = RuleMiner(args.kb_dir)
    output = miner.export(args.output)
    if not args.output:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
