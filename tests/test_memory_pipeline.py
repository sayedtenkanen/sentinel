"""Tests for Sentinel Memory pipeline modules (steps 9-18).

Covers: retriever, extractor, validator, conflict, synthesizer,
temporal, consolidation, eval, ab_framework.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sentinel.memory.conflict import ConflictResolution, MemoryConflictResolver
from sentinel.memory.consolidation import ConsolidationConfig, ConsolidationJob
from sentinel.memory.eval import MemoryEvaluator
from sentinel.memory.extractor import ExtractionConfig, MemoryExtractor
from sentinel.memory.models import (
    FeedbackEvent,
    Memory,
    MemoryCandidate,
    MemoryType,
    ReviewEvent,
)
from sentinel.memory.retriever import MemoryRetriever, RetrievalContext
from sentinel.memory.store import MemoryStore
from sentinel.memory.synthesizer import MemorySynthesizer, SynthesisConfig
from sentinel.memory.temporal import TemporalConfig, TemporalManager
from sentinel.memory.validator import MemoryValidator, ValidationConfig


def _make_memory(
    mem_type=MemoryType.CONTEXT,
    content=None,
    confidence=0.8,
    tags=None,
    created_at=None,
    last_used_at=None,
    expires_at=None,
):
    return Memory(
        type=mem_type,
        content=content or {},
        confidence=confidence,
        tags=tags or [],
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        last_used_at=last_used_at or datetime.now(timezone.utc).isoformat(),
        expires_at=expires_at,
    )


def _make_candidate(
    mem_type=MemoryType.CONTEXT,
    content=None,
    confidence=0.8,
    evidence=None,
    tags=None,
    extracted_at=None,
):
    return MemoryCandidate(
        type=mem_type,
        content=content or {},
        confidence=confidence,
        evidence=evidence or [],
        tags=tags or [],
        extracted_at=extracted_at or datetime.now(timezone.utc).isoformat(),
    )


def _make_review_event(rule_id="SEC001", finding_id="f1", language="python"):
    return ReviewEvent(
        file_path="test.py",
        finding_id=finding_id,
        rule_id=rule_id,
        severity="medium",
        agent="security",
        language=language,
    )


def _make_feedback(finding_id="f1", rating="correct", user=None):
    return FeedbackEvent(
        finding_id=finding_id,
        rating=rating,
        user=user,
    )


class TestRetriever(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(f"{self.tmpdir}/test.db")
        self.retriever = MemoryRetriever(self.store)

    def test_retrieve_empty(self):
        ctx = RetrievalContext(languages=["python"])
        result = self.retriever.retrieve(ctx)
        self.assertEqual(result.total_available, 0)
        self.assertEqual(result.memories, [])

    def test_retrieve_with_memories(self):
        mem = _make_memory(tags=["python"], content={"rule": "SEC001"})
        self.store.insert(mem)
        ctx = RetrievalContext(languages=["python"])
        result = self.retriever.retrieve(ctx)
        self.assertEqual(result.total_available, 1)
        self.assertEqual(len(result.memories), 1)

    def test_retrieve_max_limit(self):
        for _i in range(15):
            self.store.insert(_make_memory(tags=["python"]))
        ctx = RetrievalContext(languages=["python"], max_memories=5)
        result = self.retriever.retrieve(ctx)
        self.assertEqual(len(result.memories), 5)
        self.assertEqual(result.total_available, 15)

    def test_retrieve_by_rule(self):
        mem = _make_memory(mem_type=MemoryType.RULE, tags=["SEC001"])
        self.store.insert(mem)
        results = self.retriever.retrieve_by_rule("SEC001")
        self.assertEqual(len(results), 1)

    def test_retrieve_by_language(self):
        mem = _make_memory(tags=["python"])
        self.store.insert(mem)
        results = self.retriever.retrieve_by_language("python")
        self.assertEqual(len(results), 1)

    def test_retrieve_by_agent(self):
        mem = _make_memory(tags=["security"])
        self.store.insert(mem)
        results = self.retriever.retrieve_by_agent("security")
        self.assertEqual(len(results), 1)

    def test_get_preferences(self):
        mem = _make_memory(mem_type=MemoryType.PREFERENCE)
        self.store.insert(mem)
        results = self.retriever.get_preferences()
        self.assertEqual(len(results), 1)

    def test_get_context(self):
        mem = _make_memory(mem_type=MemoryType.CONTEXT)
        self.store.insert(mem)
        results = self.retriever.get_context()
        self.assertEqual(len(results), 1)

    def test_build_agent_context_empty(self):
        ctx = RetrievalContext()
        result = self.retriever.retrieve(ctx)
        self.assertEqual(result.context_for_agents, {})

    def test_build_agent_context_with_memories(self):
        mem = _make_memory(mem_type=MemoryType.RULE, tags=["python"], content={"rule_id": "SEC001"})
        self.store.insert(mem)
        ctx = RetrievalContext(languages=["python"])
        result = self.retriever.retrieve(ctx)
        self.assertIn("memory_count", result.context_for_agents)
        self.assertIn("rules", result.context_for_agents)
        self.assertIn("summary", result.context_for_agents)

    def test_summarize_memories_over_5(self):
        for _i in range(7):
            self.store.insert(_make_memory(tags=["python"]))
        ctx = RetrievalContext(languages=["python"])
        result = self.retriever.retrieve(ctx)
        self.assertIn("...and", result.context_for_agents["summary"])

    def test_build_query_tags_deduplication(self):
        ctx = RetrievalContext(languages=["python", "python"], rule_ids=["SEC001"])
        tags = self.retriever._build_query_tags(ctx)
        self.assertEqual(len(tags), len(set(tags)))


class TestExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = MemoryExtractor()

    def test_extract_empty(self):
        candidates = self.extractor.extract([], [])
        self.assertEqual(candidates, [])

    def test_mine_patterns(self):
        events = [_make_review_event(rule_id="SEC001", finding_id=f"f{i}") for i in range(5)]
        feedbacks = [_make_feedback(finding_id=f"f{i}", rating="correct") for i in range(5)]
        candidates = self.extractor.extract(events, feedbacks)
        rule_candidates = [c for c in candidates if c.type == MemoryType.RULE]
        self.assertTrue(len(rule_candidates) >= 1)
        self.assertEqual(rule_candidates[0].content["rule_id"], "SEC001")

    def test_mine_patterns_below_threshold(self):
        events = [_make_review_event(rule_id="SEC001", finding_id="f1")]
        feedbacks = [_make_feedback(finding_id="f1", rating="correct")]
        candidates = self.extractor.extract(events, feedbacks)
        rule_candidates = [c for c in candidates if c.type == MemoryType.RULE]
        self.assertEqual(len(rule_candidates), 0)

    def test_infer_preferences(self):
        feedbacks = [_make_feedback(rating="correct", user="alice") for _ in range(5)]
        candidates = self.extractor.extract([], feedbacks)
        pref_candidates = [c for c in candidates if c.type == MemoryType.PREFERENCE]
        self.assertTrue(len(pref_candidates) >= 1)

    def test_infer_preferences_below_threshold(self):
        feedbacks = [_make_feedback(rating="correct", user="alice")]
        candidates = self.extractor.extract([], feedbacks)
        pref_candidates = [c for c in candidates if c.type == MemoryType.PREFERENCE]
        self.assertEqual(len(pref_candidates), 0)

    def test_observe_context_languages(self):
        events = [_make_review_event(language="python", finding_id=f"f{i}") for i in range(6)]
        candidates = self.extractor.extract(events, [])
        ctx_candidates = [c for c in candidates if c.type == MemoryType.CONTEXT]
        self.assertTrue(len(ctx_candidates) >= 1)
        self.assertEqual(ctx_candidates[0].content["type"], "primary_language")

    def test_observe_context_directories(self):
        events = [
            ReviewEvent(file_path=f"tests/test_{i}.py", file_context="tests", finding_id=f"f{i}")
            for i in range(4)
        ]
        candidates = self.extractor.extract(events, [])
        ctx_candidates = [c for c in candidates if c.content.get("type") == "directory_pattern"]
        self.assertTrue(len(ctx_candidates) >= 1)

    def test_observe_context_below_threshold(self):
        events = [_make_review_event(language="python", finding_id="f1")]
        candidates = self.extractor.extract(events, [])
        ctx_candidates = [c for c in candidates if c.type == MemoryType.CONTEXT]
        self.assertEqual(len(ctx_candidates), 0)

    def test_custom_config(self):
        config = ExtractionConfig(pattern_min_feedbacks=1, pattern_confidence_threshold=0.5)
        extractor = MemoryExtractor(config)
        events = [_make_review_event(rule_id="SEC001", finding_id="f1")]
        feedbacks = [_make_feedback(finding_id="f1", rating="correct")]
        candidates = extractor.extract(events, feedbacks)
        rule_candidates = [c for c in candidates if c.type == MemoryType.RULE]
        self.assertTrue(len(rule_candidates) >= 1)


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.validator = MemoryValidator()

    def test_validate_empty(self):
        result = self.validator.validate([])
        self.assertEqual(result, [])

    def test_validate_passes_valid(self):
        candidate = _make_candidate(confidence=0.8, evidence=["e1", "e2", "e3"])
        result = self.validator.validate([candidate])
        self.assertEqual(len(result), 1)

    def test_validate_rejects_low_confidence(self):
        candidate = _make_candidate(confidence=0.3, evidence=["e1", "e2", "e3"])
        result = self.validator.validate([candidate])
        self.assertEqual(len(result), 0)

    def test_validate_rejects_insufficient_evidence(self):
        candidate = _make_candidate(confidence=0.8, evidence=["e1"])
        result = self.validator.validate([candidate])
        self.assertEqual(len(result), 0)

    def test_validate_uses_sample_size_from_content(self):
        candidate = _make_candidate(confidence=0.8, content={"sample_size": 5}, evidence=["e1"])
        result = self.validator.validate([candidate])
        self.assertEqual(len(result), 1)

    def test_validate_uses_total_feedbacks_from_content(self):
        candidate = _make_candidate(confidence=0.8, content={"total_feedbacks": 5}, evidence=["e1"])
        result = self.validator.validate([candidate])
        self.assertEqual(len(result), 1)

    def test_validate_rejects_stale(self):
        stale_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        candidate = _make_candidate(
            confidence=0.8, evidence=["e1", "e2", "e3"], extracted_at=stale_date
        )
        result = self.validator.validate([candidate])
        self.assertEqual(len(result), 0)

    def test_validate_bad_date_passthrough(self):
        candidate = _make_candidate(
            confidence=0.8, evidence=["e1", "e2", "e3"], extracted_at="not-a-date"
        )
        result = self.validator.validate([candidate])
        self.assertEqual(len(result), 1)

    def test_custom_config(self):
        config = ValidationConfig(min_confidence=0.3, max_age_days=60, min_sample_size=1)
        validator = MemoryValidator(config)
        candidate = _make_candidate(confidence=0.5, evidence=["e1"])
        result = validator.validate([candidate])
        self.assertEqual(len(result), 1)

    def test_validate_against_existing_ok(self):
        candidate = _make_candidate(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})
        existing = [_make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC002"})]
        valid, reason = self.validator.validate_against_existing(candidate, existing)
        self.assertTrue(valid)
        self.assertEqual(reason, "OK")

    def test_validate_against_existing_contradiction(self):
        candidate = _make_candidate(
            mem_type=MemoryType.RULE,
            content={"rule_id": "SEC001", "feedback_pattern": "correct"},
        )
        existing = [
            _make_memory(
                mem_type=MemoryType.RULE,
                content={"rule_id": "SEC001", "feedback_pattern": "incorrect"},
            )
        ]
        valid, reason = self.validator.validate_against_existing(candidate, existing)
        self.assertFalse(valid)
        self.assertIn("Contradicts", reason)

    def test_contradicts_different_type(self):
        candidate = _make_candidate(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})
        existing = _make_memory(mem_type=MemoryType.CONTEXT, content={"rule_id": "SEC001"})
        self.assertFalse(self.validator._contradicts(candidate, existing))

    def test_contradicts_same_rule_same_pattern(self):
        candidate = _make_candidate(
            mem_type=MemoryType.RULE,
            content={"rule_id": "SEC001", "feedback_pattern": "correct"},
        )
        existing = _make_memory(
            mem_type=MemoryType.RULE,
            content={"rule_id": "SEC001", "feedback_pattern": "correct"},
        )
        self.assertFalse(self.validator._contradicts(candidate, existing))

    def test_contradicts_no_pattern(self):
        candidate = _make_candidate(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})
        existing = _make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})
        self.assertFalse(self.validator._contradicts(candidate, existing))


class TestConflictResolver(unittest.TestCase):
    def setUp(self):
        self.resolver = MemoryConflictResolver()

    def test_resolve_no_conflicts(self):
        candidates = [_make_candidate(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})]
        result = self.resolver.resolve(candidates, [])
        self.assertEqual(result.conflicts_found, 0)
        self.assertEqual(len(result.resolved), 1)

    def test_resolve_with_conflict(self):
        candidate = _make_candidate(
            mem_type=MemoryType.RULE,
            content={"rule_id": "SEC001", "feedback_pattern": "correct"},
            extracted_at=(datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat(),
        )
        existing = [
            _make_memory(
                mem_type=MemoryType.RULE,
                content={"rule_id": "SEC001", "feedback_pattern": "incorrect"},
                created_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            )
        ]
        result = self.resolver.resolve([candidate], existing)
        self.assertEqual(result.conflicts_found, 1)
        self.assertEqual(result.resolutions_applied, 1)

    def test_user_preference_wins_unreachable(self):
        from sentinel.memory.conflict import MemoryConflictResolver

        resolver = MemoryConflictResolver()
        candidate = _make_candidate(mem_type=MemoryType.PREFERENCE, content={"user": "alice"})
        existing = [_make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})]
        self.assertFalse(resolver._is_conflict(candidate, existing[0]))
        self.assertTrue(resolver._user_preference_wins(candidate, existing[0]))

    def test_no_conflict_different_type(self):
        candidate = _make_candidate(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})
        existing = [_make_memory(mem_type=MemoryType.CONTEXT, content={"rule_id": "SEC001"})]
        result = self.resolver.resolve([candidate], existing)
        self.assertEqual(result.conflicts_found, 0)

    def test_no_conflict_different_rule(self):
        candidate = _make_candidate(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})
        existing = [_make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC002"})]
        result = self.resolver.resolve([candidate], existing)
        self.assertEqual(result.conflicts_found, 0)

    def test_preference_conflict(self):
        candidate = _make_candidate(
            mem_type=MemoryType.PREFERENCE,
            content={"user": "alice", "preferred_feedback": "correct"},
        )
        existing = [
            _make_memory(
                mem_type=MemoryType.PREFERENCE,
                content={"user": "alice", "preferred_feedback": "incorrect"},
            )
        ]
        result = self.resolver.resolve([candidate], existing)
        self.assertEqual(result.conflicts_found, 1)

    def test_fresh_wins_over_stale(self):
        candidate = _make_candidate(
            mem_type=MemoryType.RULE,
            content={"rule_id": "SEC001", "feedback_pattern": "correct"},
        )
        stale_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        existing = [
            _make_memory(
                mem_type=MemoryType.RULE,
                content={"rule_id": "SEC001", "feedback_pattern": "incorrect"},
                last_used_at=stale_date,
            )
        ]
        result = self.resolver.resolve([candidate], existing)
        self.assertEqual(result.conflicts_found, 1)

    def test_conflict_resolution_dataclass(self):
        cr = ConflictResolution()
        self.assertEqual(cr.resolved, [])
        self.assertEqual(cr.conflicts_found, 0)

    def test_candidate_to_memory(self):
        candidate = _make_candidate(
            mem_type=MemoryType.RULE, content={"k": "v"}, confidence=0.9, tags=["t1"]
        )
        mem = self.resolver._candidate_to_memory(candidate)
        self.assertEqual(mem.type, MemoryType.RULE)
        self.assertEqual(mem.confidence, 0.9)
        self.assertEqual(mem.tags, ["t1"])


class TestSynthesizer(unittest.TestCase):
    def setUp(self):
        self.synthesizer = MemorySynthesizer()

    def test_synthesize_empty(self):
        result = self.synthesizer.synthesize([])
        self.assertEqual(result, [])

    def test_synthesize_single_memory(self):
        mem = _make_memory(mem_type=MemoryType.CONTEXT)
        result = self.synthesizer.synthesize([mem])
        self.assertEqual(len(result), 1)

    def test_merge_rules_same_rule(self):
        mem1 = _make_memory(
            mem_type=MemoryType.RULE,
            content={"rule_id": "SEC001", "evidence": ["e1"]},
            confidence=0.9,
        )
        mem2 = _make_memory(
            mem_type=MemoryType.RULE,
            content={"rule_id": "SEC001", "evidence": ["e2"]},
            confidence=0.7,
        )
        result = self.synthesizer.synthesize([mem1, mem2])
        self.assertEqual(len(result), 1)
        self.assertIn("SEC001", result[0].content["rule_id"])
        self.assertEqual(result[0].content["source_count"], 2)

    def test_merge_rules_different_rules(self):
        mem1 = _make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"}, confidence=0.9)
        mem2 = _make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC002"}, confidence=0.7)
        result = self.synthesizer.synthesize([mem1, mem2])
        self.assertEqual(len(result), 2)

    def test_merge_preferences_same_user(self):
        mem1 = _make_memory(
            mem_type=MemoryType.PREFERENCE,
            content={"user": "alice", "evidence": ["e1"]},
            confidence=0.9,
        )
        mem2 = _make_memory(
            mem_type=MemoryType.PREFERENCE,
            content={"user": "alice", "evidence": ["e2"]},
            confidence=0.7,
        )
        result = self.synthesizer.synthesize([mem1, mem2])
        self.assertEqual(len(result), 1)

    def test_merge_preferences_different_users(self):
        mem1 = _make_memory(
            mem_type=MemoryType.PREFERENCE, content={"user": "alice"}, confidence=0.9
        )
        mem2 = _make_memory(mem_type=MemoryType.PREFERENCE, content={"user": "bob"}, confidence=0.7)
        result = self.synthesizer.synthesize([mem1, mem2])
        self.assertEqual(len(result), 2)

    def test_compress_for_context_empty(self):
        result = self.synthesizer.compress_for_context([])
        self.assertEqual(result, "")

    def test_compress_for_context_with_memories(self):
        mems = [_make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})]
        result = self.synthesizer.compress_for_context(mems)
        self.assertIn("SEC001", result)

    def test_compress_for_context_overflow(self):
        mems = [
            _make_memory(
                mem_type=MemoryType.RULE,
                content={"rule_id": f"SEC{i:03d}", "feedback_pattern": "correct" * 10},
            )
            for i in range(20)
        ]
        result = self.synthesizer.compress_for_context(mems, max_tokens=20)
        self.assertIn("more memories", result)

    def test_memory_to_summary_types(self):
        for mt in MemoryType:
            content = {"rule_id": "SEC001"} if mt == MemoryType.RULE else {}
            if mt == MemoryType.PREFERENCE:
                content = {"user": "alice", "preferred_feedback": "correct"}
            if mt == MemoryType.CONTEXT:
                content = {"type": "primary_language"}
            mem = _make_memory(mem_type=mt, content=content)
            summary = self.synthesizer._memory_to_summary(mem)
            self.assertIn(mt.value, summary)

    def test_custom_config(self):
        config = SynthesisConfig(merge_same_rule=False, merge_same_preference=False)
        synth = MemorySynthesizer(config)
        mem1 = _make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})
        mem2 = _make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})
        result = synth.synthesize([mem1, mem2])
        self.assertEqual(len(result), 2)


class TestTemporal(unittest.TestCase):
    def setUp(self):
        self.temporal = TemporalManager()

    def test_find_expired_empty(self):
        result = self.temporal.find_expired([])
        self.assertEqual(result, [])

    def test_filter_active_empty(self):
        result = self.temporal.filter_active([])
        self.assertEqual(result, [])

    def test_find_archivable_empty(self):
        result = self.temporal.find_archivable([])
        self.assertEqual(result, [])

    def test_expired_by_expires_at(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        mem = _make_memory(expires_at=past)
        result = self.temporal.find_expired([mem])
        self.assertEqual(len(result), 1)

    def test_not_expired_by_expires_at(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        mem = _make_memory(expires_at=future)
        result = self.temporal.find_expired([mem])
        self.assertEqual(len(result), 0)

    def test_expired_bad_expires_at(self):
        mem = _make_memory(expires_at="not-a-date")
        result = self.temporal.find_expired([mem])
        self.assertEqual(len(result), 0)

    def test_expired_by_age_context(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        mem = _make_memory(mem_type=MemoryType.CONTEXT, created_at=old_date)
        result = self.temporal.find_expired([mem])
        self.assertEqual(len(result), 1)

    def test_not_expired_preference_never(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=999)).isoformat()
        mem = _make_memory(mem_type=MemoryType.PREFERENCE, created_at=old_date)
        result = self.temporal.find_expired([mem])
        self.assertEqual(len(result), 0)

    def test_archivable_context(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=160)).isoformat()
        mem = _make_memory(mem_type=MemoryType.CONTEXT, created_at=old_date)
        result = self.temporal.find_archivable([mem])
        self.assertEqual(len(result), 1)

    def test_not_archivable_recent(self):
        mem = _make_memory(mem_type=MemoryType.CONTEXT)
        result = self.temporal.find_archivable([mem])
        self.assertEqual(len(result), 0)

    def test_archivable_bad_date(self):
        mem = _make_memory(mem_type=MemoryType.CONTEXT, created_at="bad")
        result = self.temporal.find_archivable([mem])
        self.assertEqual(len(result), 0)

    def test_calculate_decay_fresh(self):
        mem = _make_memory()
        decay = self.temporal.calculate_decay(mem)
        self.assertGreater(decay, 0.9)

    def test_calculate_decay_preference_never(self):
        mem = _make_memory(mem_type=MemoryType.PREFERENCE)
        decay = self.temporal.calculate_decay(mem)
        self.assertEqual(decay, 1.0)

    def test_calculate_decay_bad_date(self):
        mem = _make_memory(created_at="bad")
        decay = self.temporal.calculate_decay(mem)
        self.assertEqual(decay, 1.0)

    def test_apply_decay_to_confidence(self):
        mem = _make_memory(confidence=0.8)
        result = self.temporal.apply_decay_to_confidence(mem)
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 0.8)

    def test_get_age_days(self):
        mem = _make_memory()
        age = self.temporal.get_age_days(mem)
        self.assertEqual(age, 0)

    def test_get_age_days_bad_date(self):
        mem = _make_memory(created_at="bad")
        age = self.temporal.get_age_days(mem)
        self.assertEqual(age, 0)

    def test_custom_config(self):
        config = TemporalConfig(
            preference_half_life_days=100,
            context_half_life_days=30,
            pattern_half_life_days=10,
            temporal_half_life_days=7,
            preference_archive_days=200,
            context_archive_days=60,
            pattern_archive_days=20,
            temporal_archive_days=10,
        )
        temporal = TemporalManager(config)
        mem = _make_memory(mem_type=MemoryType.CONTEXT)
        decay = temporal.calculate_decay(mem)
        self.assertGreater(decay, 0)


class TestConsolidation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(f"{self.tmpdir}/test.db")

    def test_run_once_empty(self):
        job = ConsolidationJob(self.store)
        result = job.run_once()
        self.assertEqual(result["candidates_extracted"], 0)
        self.assertEqual(result["new_stored"], 0)

    def test_run_once_with_events(self):
        job = ConsolidationJob(self.store)
        events = [_make_review_event(rule_id="SEC001", finding_id=f"f{i}") for i in range(5)]
        feedbacks = [_make_feedback(finding_id=f"f{i}", rating="correct") for i in range(5)]
        result = job.run_once(events, feedbacks)
        self.assertGreater(result["candidates_extracted"], 0)

    def test_filter_new_memories(self):
        job = ConsolidationJob(self.store)
        existing = [_make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"})]
        candidates = [
            _make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC001"}),
            _make_memory(mem_type=MemoryType.RULE, content={"rule_id": "SEC002"}),
        ]
        new = job._filter_new_memories(candidates, existing)
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].content["rule_id"], "SEC002")

    def test_start_stop(self):
        config = ConsolidationConfig(interval_seconds=3600)
        job = ConsolidationJob(self.store, config)
        job.start()
        self.assertTrue(job._running)
        job.stop()
        self.assertFalse(job._running)

    def test_start_disabled(self):
        config = ConsolidationConfig(enabled=False)
        job = ConsolidationJob(self.store, config)
        job.start()
        self.assertFalse(job._running)

    def test_stop_no_timer(self):
        job = ConsolidationJob(self.store)
        job.stop()
        self.assertFalse(job._running)

    def test_run_timer_not_running(self):
        job = ConsolidationJob(self.store)
        job._running = False
        job._run_timer()

    def test_schedule_next_not_running(self):
        job = ConsolidationJob(self.store)
        job._running = False
        job._schedule_next()


class TestEvaluator(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(f"{self.tmpdir}/test.db")
        self.evaluator = MemoryEvaluator(self.store)

    def test_evaluate_empty(self):
        result = self.evaluator.evaluate()
        self.assertEqual(result.memories_evaluated, 0)
        self.assertIn("store_health", result.details)

    def test_evaluate_with_memories(self):
        self.store.insert(_make_memory(tags=["python"]))
        result = self.evaluator.evaluate()
        self.assertEqual(result.memories_evaluated, 1)
        self.assertIn("by_type", result.details)

    def test_evaluate_with_queries(self):
        mem = _make_memory(tags=["python"])
        self.store.insert(mem)
        queries = [{"tags": ["python"], "expected_memories": [mem.id]}]
        result = self.evaluator.evaluate(queries)
        self.assertEqual(result.true_positives, 1)
        self.assertGreater(result.precision, 0)

    def test_evaluate_queries_no_match(self):
        queries = [{"tags": ["python"], "expected_memories": ["nonexistent"]}]
        result = self.evaluator.evaluate(queries)
        self.assertEqual(result.false_negatives, 1)

    def test_evaluate_queries_with_type(self):
        mem = _make_memory(mem_type=MemoryType.RULE, tags=["SEC001"])
        self.store.insert(mem)
        queries = [{"tags": ["SEC001"], "type": MemoryType.RULE, "expected_memories": [mem.id]}]
        result = self.evaluator.evaluate(queries)
        self.assertEqual(result.true_positives, 1)

    def test_precision_at_k(self):
        mem = _make_memory(tags=["python"])
        self.store.insert(mem)
        result = self.evaluator.precision_at_k(["python"], [mem.id], k=5)
        self.assertEqual(result, 0.2)

    def test_precision_at_k_zero(self):
        result = self.evaluator.precision_at_k([], [], k=0)
        self.assertEqual(result, 0.0)

    def test_coverage_empty(self):
        result = self.evaluator.coverage()
        self.assertEqual(result["total"], 0)

    def test_coverage_with_memories(self):
        self.store.insert(_make_memory(mem_type=MemoryType.RULE))
        self.store.insert(_make_memory(mem_type=MemoryType.CONTEXT))
        result = self.evaluator.coverage()
        self.assertEqual(result["total"], 2)
        self.assertIn("rule", result["by_type"])

    def test_avg_confidence_empty(self):
        result = self.evaluator._avg_confidence([])
        self.assertEqual(result, 0.0)

    def test_query_store_with_type(self):
        mem = _make_memory(mem_type=MemoryType.RULE, tags=["SEC001"])
        self.store.insert(mem)
        result = self.evaluator._query_store(["SEC001"], MemoryType.RULE)
        self.assertEqual(len(result), 1)

    def test_query_store_without_type(self):
        mem = _make_memory(tags=["python"])
        self.store.insert(mem)
        result = self.evaluator._query_store(["python"], None)
        self.assertEqual(len(result), 1)


class TestABFramework(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(f"{self.tmpdir}/test.db")

    def test_compare_reports_none(self):
        from sentinel.memory.ab_framework import ABFramework

        fw = ABFramework()
        comparison = fw._compare_reports(None, None)
        self.assertEqual(comparison["findings_with_memory"], 0)
        self.assertEqual(comparison["findings_without_memory"], 0)

    def test_generate_recommendation_improved(self):
        from sentinel.memory.ab_framework import ABFramework

        fw = ABFramework()
        rec = fw._generate_recommendation({"score_delta": 10, "findings_delta": 0})
        self.assertIn("improved", rec)

    def test_generate_recommendation_degraded(self):
        from sentinel.memory.ab_framework import ABFramework

        fw = ABFramework()
        rec = fw._generate_recommendation({"score_delta": -10, "findings_delta": 0})
        self.assertIn("degraded", rec)

    def test_generate_recommendation_reduced(self):
        from sentinel.memory.ab_framework import ABFramework

        fw = ABFramework()
        rec = fw._generate_recommendation({"score_delta": 0, "findings_delta": 5})
        self.assertIn("reduced", rec)

    def test_generate_recommendation_added(self):
        from sentinel.memory.ab_framework import ABFramework

        fw = ABFramework()
        rec = fw._generate_recommendation({"score_delta": 0, "findings_delta": -5})
        self.assertIn("added", rec)

    def test_generate_recommendation_no_diff(self):
        from sentinel.memory.ab_framework import ABFramework

        fw = ABFramework()
        rec = fw._generate_recommendation({"score_delta": 0, "findings_delta": 0})
        self.assertIn("no_significant_difference", rec)


if __name__ == "__main__":
    unittest.main()
