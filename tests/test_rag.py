import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sentinel.rag.knowledge_base import KnowledgeBase, chunk_code
from sentinel.rag.retriever import Retriever
from sentinel.rag.vector_store import TfidfVectorStore, tokenize


class TestTokenize(unittest.TestCase):
    def test_basic_tokenization(self):
        tokens = tokenize("def foo_bar(x, y): pass")
        self.assertIn("def", tokens)
        self.assertIn("foo_bar", tokens)

    def test_strips_short_tokens(self):
        tokens = tokenize("a b c def")
        self.assertEqual(tokens, ["def"])

    def test_removes_digits_only(self):
        tokens = tokenize("123 abc 456")
        self.assertEqual(tokens, ["abc"])

    def test_lowercase(self):
        tokens = tokenize("FooBar")
        self.assertEqual(tokens, ["foobar"])

    def test_handles_empty(self):
        self.assertEqual(tokenize(""), [])


class TestTfidfVectorStore(unittest.TestCase):
    def setUp(self):
        self.store = TfidfVectorStore()

    def test_add_and_search(self):
        self.store.add_document("1", "def foo(): pass", {"file": "a.py"})
        self.store.add_document("2", "def bar(): pass", {"file": "b.py"})
        results = self.store.search("foo", top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "1")
        self.assertGreater(results[0]["score"], 0)

    def test_search_empty_store(self):
        self.assertEqual(self.store.search("hello"), [])

    def test_search_no_match(self):
        self.store.add_document("1", "python code", {})
        results = self.store.search("javascript")
        self.assertEqual(results, [])

    def test_remove_document(self):
        self.store.add_document("1", "def foo(): pass")
        self.store.add_document("2", "def bar(): pass")
        self.store.remove_document("1")
        self.assertEqual(len(self.store.documents), 1)

    def test_save_and_load(self):
        self.store.add_document("1", "def foo(): pass", {"file": "a.py"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "store.json")
            self.store.save(path)
            loaded = TfidfVectorStore.load(path)
            self.assertEqual(len(loaded.documents), 1)
            self.assertEqual(loaded.documents[0]["id"], "1")
            self.assertEqual(loaded.documents[0]["metadata"]["file"], "a.py")

    def test_short_document_skipped(self):
        self.store.add_document("1", "a")
        self.assertEqual(len(self.store.documents), 0)

    def test_top_k_limits(self):
        for i in range(10):
            self.store.add_document(str(i), f"def func{i}(): pass")
        results = self.store.search("func", top_k=3)
        self.assertLessEqual(len(results), 3)

    def test_identical_similarity(self):
        self.store.add_document("1", "def foo(x, y): return x + y")
        results = self.store.search("def foo(x, y): return x + y", top_k=5)
        self.assertEqual(results[0]["id"], "1")
        self.assertAlmostEqual(results[0]["score"], 1.0, places=3)


class TestChunkCode(unittest.TestCase):
    def test_small_code_stays_one_chunk(self):
        chunks = chunk_code("x = 1\ny = 2\n", min_chars=100)
        self.assertEqual(len(chunks), 1)

    def test_splits_at_function_boundary(self):
        code = "def a(): pass\n" * 30
        chunks = chunk_code(code, min_chars=50)
        self.assertGreater(len(chunks), 1)

    def test_each_chunk_has_lines(self):
        code = "line1\nline2\nline3\nline4\nline5\n"
        chunks = chunk_code(code, min_chars=2, max_chars=200)
        for _, start, end in chunks:
            self.assertGreaterEqual(end, start)


class TestKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()

    def test_add_and_search_finding(self):
        cid = self.kb.add_finding("def insecure(): pass", {"rule_id": "SEC001", "severity": "high"})
        self.assertIn(cid, self.kb.findings)
        results = self.kb.search_similar("def insecure(): pass")
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("findings", results[0])

    def test_search_returns_findings(self):
        self.kb.add_finding("def foo(): pass", {"rule_id": "STY001"})
        results = self.kb.search_similar("def foo(): pass")
        self.assertEqual(results[0]["findings"][0]["rule_id"], "STY001")

    def test_ingest_findings(self):
        source = "def foo():\n    pass\ndef bar():\n    pass\n"
        findings = [
            {"rule_id": "STY001", "line": 1},
            {"rule_id": "STY002", "line": 3},
        ]
        count = self.kb.ingest_findings("test.py", source, findings)
        self.assertGreater(count, 0)

    def test_save_and_load(self):
        self.kb.add_finding("def foo(): pass", {"rule_id": "SEC001"})
        with tempfile.TemporaryDirectory() as d:
            self.kb.save(d)
            loaded = KnowledgeBase.load(d)
            self.assertIn(next(iter(self.kb.findings.keys())), loaded.findings)

    def test_empty_kb_search(self):
        results = self.kb.search_similar("def anything(): pass")
        self.assertEqual(results, [])


class TestRetriever(unittest.TestCase):
    def setUp(self):
        kb = KnowledgeBase()
        kb.add_finding(
            "def foo(): pass", {"rule_id": "SEC001", "message": "test", "severity": "high"}
        )
        self.retriever = Retriever(kb)

    def test_retrieve_context(self):
        results = self.retriever.retrieve_context("def foo(): pass")
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("findings", results[0])
        self.assertIn("code_snippet", results[0])

    def test_build_prompt_context(self):
        results = self.retriever.retrieve_context("def foo(): pass")
        prompt = self.retriever.build_prompt_context(results)
        self.assertIn("SEC001", prompt)
        self.assertIn("Relevant past findings", prompt)

    def test_build_prompt_context_empty(self):
        self.assertEqual(self.retriever.build_prompt_context([]), "")


class TestLlmReviewAgent(unittest.TestCase):
    def test_disabled_when_no_api_key(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent(api_key="")
        self.assertFalse(agent._check_available())

    def test_enabled_with_api_key(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent(api_key="sk-test123")
        self.assertTrue(agent._check_available())

    def test_analyze_returns_empty_when_disabled(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent(api_key="")
        ctx = MagicMock()
        ctx.files = [{"path": "test.py", "content": "x = 1"}]
        self.assertEqual(agent.analyze(ctx), [])

    def test_parse_response_with_json_array(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent(api_key="sk-test")
        response = '[{"line": 5, "severity": "high", "rule_id": "LLM001", "message": "test"}]'
        parsed = agent._parse_response(response)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["rule_id"], "LLM001")

    def test_parse_response_with_fences(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent(api_key="sk-test")
        response = (
            '```json\n[{"line": 1, "severity": "low", "rule_id": "LLM002", "message": "x"}]\n```'
        )
        parsed = agent._parse_response(response)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["rule_id"], "LLM002")

    def test_parse_response_invalid_json(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent(api_key="sk-test")
        response = "this is not json"
        parsed = agent._parse_response(response)
        self.assertEqual(parsed, [])

    def test_parse_response_single_dict(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent(api_key="sk-test")
        response = '{"line": 3, "severity": "medium", "rule_id": "LLM003", "message": "test"}'
        parsed = agent._parse_response(response)
        self.assertEqual(len(parsed), 1)

    def test_get_config_schema(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent()
        schema = agent.get_config_schema()
        self.assertIn("api_key", schema)
        self.assertIn("model", schema)
        self.assertIn("rag_top_k", schema)

    @patch("urllib.request.urlopen")
    def test_call_llm_success(self, mock_urlopen):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent(api_key="sk-test")

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": '[{"line": 1, "severity": "low", "rule_id": "LLM001", "message": "test"}]'
                        }
                    }
                ]
            }
        ).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        response = agent._call_llm("review this code")
        self.assertIn("LLM001", response)

    def test_build_prompt_without_context(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        agent = LlmReviewAgent(api_key="sk-test")
        prompt = agent._build_prompt("x = 1", [], "test.py")
        self.assertIn("test.py", prompt)
        self.assertIn("x = 1", prompt)
        self.assertIn("JSON array", prompt)

    def test_build_prompt_with_rag_context(self):
        from sentinel.agents.llm_review import LlmReviewAgent

        kb = KnowledgeBase()
        kb.add_finding(
            "def foo(): pass", {"rule_id": "SEC001", "message": "bad", "severity": "high"}
        )
        from sentinel.rag.retriever import Retriever

        retriever = Retriever(kb)
        agent = LlmReviewAgent(api_key="sk-test", retriever=retriever)
        results = retriever.retrieve_context("def foo(): pass")
        prompt = agent._build_prompt("def foo(): pass", results, "test.py")
        self.assertIn("SEC001", prompt)
        self.assertIn("Relevant past findings", prompt)


class TestRegistryLlmAgent(unittest.TestCase):
    def test_llm_review_in_default_registry(self):
        from sentinel.govern.registry import AgentRegistry

        registry = AgentRegistry.default()
        info = registry.get("llm-review")
        self.assertIsNotNone(info)
        self.assertEqual(info.name, "llm-review")
        self.assertIn("llm", info.tags)
        self.assertIn("rag", info.capabilities)

    def test_llm_review_config_schema(self):
        from sentinel.govern.registry import AgentRegistry

        registry = AgentRegistry.default()
        info = registry.get("llm-review")
        self.assertIn("api_key", info.config_schema)
        self.assertIn("model", info.config_schema)

    def test_disabled_choice_includes_llm(self):
        from sentinel.deploy.runner import create_parser

        parser = create_parser()
        for action in parser._actions:
            if action.dest == "disable_agent":
                self.assertIn("llm-review", action.choices)


class TestRunnerLlmIntegration(unittest.TestCase):
    def test_no_api_key_no_llm_agent(self):
        from sentinel.deploy.runner import _setup_agents

        agents = _setup_agents({}, set(), None)
        agent_names = [a.name for a in agents]
        self.assertNotIn("llm-review", agent_names)

    def test_with_api_key_adds_llm_agent(self):
        from sentinel.deploy.runner import _setup_agents

        class FakeArgs:
            llm_api_key = "sk-test"
            llm_model = "gpt-4o-mini"
            rag_kb_dir = None

        agents = _setup_agents({}, set(), FakeArgs())
        agent_names = [a.name for a in agents]
        self.assertIn("llm-review", agent_names)

    def test_with_api_key_but_disabled(self):
        from sentinel.deploy.runner import _setup_agents

        class FakeArgs:
            llm_api_key = "sk-test"
            llm_model = "gpt-4o-mini"
            rag_kb_dir = None

        agents = _setup_agents({}, {"llm-review"}, FakeArgs())
        agent_names = [a.name for a in agents]
        self.assertNotIn("llm-review", agent_names)
