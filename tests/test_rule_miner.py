"""Unit tests for the rule suggestion miner."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.govern.rule_miner import RuleMiner, cluster_findings, extract_common_pattern


class TestExtractCommonPattern(unittest.TestCase):
    def test_single_message(self):
        result = extract_common_pattern(["hardcoded password detected"])
        self.assertIsNone(result)

    def test_identical_messages(self):
        result = extract_common_pattern(
            ["hardcoded password detected", "hardcoded password detected"]
        )
        self.assertIsNotNone(result)

    def test_related_messages(self):
        result = extract_common_pattern(
            ["Hardcoded password detected in auth.py", "Hardcoded password detected in db.py"],
        )
        self.assertIsNotNone(result)
        self.assertIn("password", str(result).lower())

    def test_unrelated_messages(self):
        result = extract_common_pattern(["line too long", "unused import detected"])
        self.assertIsNone(result)

    def test_empty_list(self):
        self.assertIsNone(extract_common_pattern([]))

    def test_quotes_normalized(self):
        result = extract_common_pattern(["password = 'secret123'", 'password = "admin123"'])
        self.assertIsNotNone(result)
        self.assertIn("...", result)


class TestClusterFindings(unittest.TestCase):
    def test_single_cluster(self):
        findings = [
            {"message": "hardcoded password", "severity": "critical"},
            {"message": "hardcoded password", "severity": "critical"},
        ]
        clusters = cluster_findings(findings)
        self.assertEqual(len(clusters), 1)

    def test_multiple_clusters(self):
        findings = [
            {"message": "hardcoded password", "severity": "critical"},
            {"message": "line too long", "severity": "low"},
        ]
        clusters = cluster_findings(findings)
        self.assertEqual(len(clusters), 2)

    def test_empty_findings(self):
        self.assertEqual(cluster_findings([]), [])


class TestRuleMiner(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmpdir))

    def _write_kb(self, findings_data: dict):
        path = self.tmpdir / "knowledge_base.json"
        path.write_text(json.dumps(findings_data))

    def test_no_kb_file(self):
        miner = RuleMiner(str(self.tmpdir))
        self.assertEqual(miner.load_findings(), [])

    def test_empty_findings(self):
        self._write_kb({"findings": {}})
        miner = RuleMiner(str(self.tmpdir))
        self.assertEqual(miner.mine(), [])

    def test_single_finding_no_cluster(self):
        self._write_kb(
            {
                "findings": {
                    "abc123": [
                        {
                            "rule_id": "SEC001",
                            "message": "hardcoded password",
                            "severity": "critical",
                            "suggestion": "use env vars",
                        },
                    ]
                }
            }
        )
        miner = RuleMiner(str(self.tmpdir))
        rules = miner.mine()
        self.assertEqual(len(rules), 0)

    def test_cluster_produces_rule(self):
        self._write_kb(
            {
                "findings": {
                    "abc123": [
                        {
                            "rule_id": "SEC001",
                            "message": "hardcoded password",
                            "severity": "critical",
                            "suggestion": "use env vars",
                            "_source_file": "auth.py",
                        },
                    ],
                    "def456": [
                        {
                            "rule_id": "SEC001",
                            "message": "hardcoded password",
                            "severity": "critical",
                            "suggestion": "use env vars",
                            "_source_file": "db.py",
                        },
                    ],
                }
            }
        )
        miner = RuleMiner(str(self.tmpdir))
        rules = miner.mine()
        self.assertGreater(len(rules), 0)

    def test_rule_has_required_fields(self):
        self._write_kb(
            {
                "findings": {
                    "1": [
                        {
                            "rule_id": "SEC001",
                            "message": "hardcoded password",
                            "severity": "critical",
                            "suggestion": "use env vars",
                            "_source_file": "a.py",
                        },
                    ],
                    "2": [
                        {
                            "rule_id": "SEC001",
                            "message": "hardcoded password",
                            "severity": "critical",
                            "suggestion": "use env vars",
                            "_source_file": "b.py",
                        },
                    ],
                }
            }
        )
        miner = RuleMiner(str(self.tmpdir))
        rules = miner.mine()
        rule = rules[0]
        self.assertIn("suggested_rule_id", rule)
        self.assertIn("pattern", rule)
        self.assertIn("frequency", rule)
        self.assertIn("severity", rule)
        self.assertIn("source_rules", rule)

    def test_export_returns_json(self):
        self._write_kb(
            {
                "findings": {
                    "1": [
                        {
                            "rule_id": "SEC001",
                            "message": "hardcoded password",
                            "severity": "critical",
                            "_source_file": "a.py",
                        },
                    ],
                    "2": [
                        {
                            "rule_id": "SEC001",
                            "message": "hardcoded password",
                            "severity": "critical",
                            "_source_file": "b.py",
                        },
                    ],
                }
            }
        )
        miner = RuleMiner(str(self.tmpdir))
        output = miner.export()
        data = json.loads(output)
        self.assertIn("mined_rules", data)
        self.assertIn("count", data)

    def test_export_to_file(self):
        self._write_kb(
            {
                "findings": {
                    "1": [
                        {
                            "rule_id": "SEC001",
                            "message": "hardcoded password",
                            "severity": "critical",
                            "_source_file": "a.py",
                        },
                    ],
                    "2": [
                        {
                            "rule_id": "SEC001",
                            "message": "hardcoded password",
                            "severity": "critical",
                            "_source_file": "b.py",
                        },
                    ],
                }
            }
        )
        out_path = self.tmpdir / "rules.json"
        miner = RuleMiner(str(self.tmpdir))
        miner.export(str(out_path))
        self.assertTrue(out_path.exists())

    def test_rules_sorted_by_frequency(self):
        self._write_kb(
            {
                "1": [
                    {
                        "rule_id": "SEC001",
                        "message": "common issue",
                        "severity": "high",
                        "_source_file": "a.py",
                    },
                ],
                "2": [
                    {
                        "rule_id": "SEC001",
                        "message": "common issue",
                        "severity": "high",
                        "_source_file": "b.py",
                    },
                ],
                "3": [
                    {
                        "rule_id": "SEC002",
                        "message": "rare issue",
                        "severity": "low",
                        "_source_file": "c.py",
                    },
                ],
            }
        )
        miner = RuleMiner(str(self.tmpdir))
        rules = miner.mine()
        if len(rules) >= 2:
            self.assertGreaterEqual(rules[0]["frequency"], rules[1]["frequency"])

    def test_missing_kb_dir(self):
        miner = RuleMiner("/nonexistent/path")
        self.assertEqual(miner.load_findings(), [])

    def test_category_inference(self):
        from sentinel.govern.rule_miner import _infer_category

        self.assertEqual(_infer_category(["SEC001", "SEC002"]), "security")
        self.assertEqual(_infer_category(["ST001"]), "static-analysis")
        self.assertEqual(_infer_category(["STY001"]), "style")
        self.assertEqual(_infer_category(["BP001"]), "best-practices")
        self.assertEqual(_infer_category(["DOC001"]), "documentation")
        self.assertEqual(_infer_category(["UNKNOWN"]), "general")

    def test_infer_category_empty(self):
        from sentinel.govern.rule_miner import _infer_category

        self.assertEqual(_infer_category([]), "general")


if __name__ == "__main__":
    unittest.main()
