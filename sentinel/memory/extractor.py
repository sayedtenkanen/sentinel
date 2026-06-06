"""Extraction node for Sentinel Memory pipeline.

Extracts memory candidates from review events and feedback using
pattern mining, preference inference, and context observation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .models import FeedbackEvent, MemoryCandidate, MemoryType, ReviewEvent


@dataclass
class ExtractionConfig:
    """Configuration for memory extraction."""

    pattern_min_feedbacks: int = 3
    pattern_confidence_threshold: float = 0.7
    preference_confidence_threshold: float = 0.6
    context_confidence_threshold: float = 0.8


class MemoryExtractor:
    """Extracts memory candidates from review events and feedback.

    Usage:
        extractor = MemoryExtractor()
        candidates = extractor.extract(events, feedbacks)
    """

    def __init__(self, config: ExtractionConfig | None = None):
        self.config = config or ExtractionConfig()

    def extract(
        self,
        review_events: list[ReviewEvent],
        feedback_events: list[FeedbackEvent],
    ) -> list[MemoryCandidate]:
        """Extract memory candidates from events and feedback."""
        candidates: list[MemoryCandidate] = []

        candidates.extend(self._mine_patterns(review_events, feedback_events))
        candidates.extend(self._infer_preferences(feedback_events))
        candidates.extend(self._observe_context(review_events))

        return candidates

    def _mine_patterns(
        self,
        review_events: list[ReviewEvent],
        feedback_events: list[FeedbackEvent],
    ) -> list[MemoryCandidate]:
        """Mine patterns from feedback on findings.

        Looks for consistent feedback (same rule, same outcome) across
        multiple reviews to identify reliable patterns.
        """
        candidates: list[MemoryCandidate] = []

        feedback_by_finding: dict[str, list[FeedbackEvent]] = {}
        for fb in feedback_events:
            if fb.finding_id not in feedback_by_finding:
                feedback_by_finding[fb.finding_id] = []
            feedback_by_finding[fb.finding_id].append(fb)

        rule_feedback: dict[str, list[str]] = {}
        for finding_id, feedbacks in feedback_by_finding.items():
            for fb in feedbacks:
                event = next((e for e in review_events if e.finding_id == finding_id), None)
                if event:
                    rule_id = event.rule_id
                    if rule_id not in rule_feedback:
                        rule_feedback[rule_id] = []
                    rule_feedback[rule_id].append(fb.rating)

        for rule_id, ratings in rule_feedback.items():
            if len(ratings) < self.config.pattern_min_feedbacks:
                continue

            rating_counts = Counter(ratings)
            most_common_rating, count = rating_counts.most_common(1)[0]
            confidence = count / len(ratings)

            if confidence >= self.config.pattern_confidence_threshold:
                candidates.append(
                    MemoryCandidate(
                        type=MemoryType.RULE,
                        content={
                            "rule_id": rule_id,
                            "feedback_pattern": most_common_rating,
                            "sample_size": len(ratings),
                        },
                        evidence=[f"rating_{r}" for r in ratings],
                        confidence=confidence,
                        source="pattern_mining",
                        tags=[rule_id],
                    )
                )

        return candidates

    def _infer_preferences(self, feedback_events: list[FeedbackEvent]) -> list[MemoryCandidate]:
        """Infer user preferences from consistent feedback patterns."""
        candidates: list[MemoryCandidate] = []

        user_ratings: dict[str, list[str]] = {}
        for fb in feedback_events:
            user = fb.user or "anonymous"
            if user not in user_ratings:
                user_ratings[user] = []
            user_ratings[user].append(fb.rating)

        for user, ratings in user_ratings.items():
            if len(ratings) < 3:
                continue

            rating_counts = Counter(ratings)
            most_common_rating, count = rating_counts.most_common(1)[0]
            confidence = count / len(ratings)

            if confidence >= self.config.preference_confidence_threshold:
                candidates.append(
                    MemoryCandidate(
                        type=MemoryType.PREFERENCE,
                        content={
                            "user": user,
                            "preferred_feedback": most_common_rating,
                            "total_feedbacks": len(ratings),
                        },
                        evidence=ratings,
                        confidence=confidence,
                        source="preference_inference",
                        tags=["preference", user],
                    )
                )

        return candidates

    def _observe_context(self, review_events: list[ReviewEvent]) -> list[MemoryCandidate]:
        """Observe project context from file patterns and structure."""
        candidates: list[MemoryCandidate] = []

        language_counts: Counter[str] = Counter()
        context_counts: Counter[str] = Counter()

        for event in review_events:
            if event.language:
                language_counts[event.language] += 1
            if event.file_context:
                context_counts[event.file_context] += 1

        for lang, count in language_counts.most_common():
            if count >= 5:
                confidence = min(1.0, count / 20)
                candidates.append(
                    MemoryCandidate(
                        type=MemoryType.CONTEXT,
                        content={
                            "type": "primary_language",
                            "language": lang,
                            "file_count": count,
                        },
                        evidence=[f"lang:{lang}:{count}"],
                        confidence=confidence,
                        source="context_observation",
                        tags=[lang, "project_context"],
                    )
                )

        for ctx_type, count in context_counts.most_common():
            if count >= 3:
                confidence = min(1.0, count / 15)
                candidates.append(
                    MemoryCandidate(
                        type=MemoryType.CONTEXT,
                        content={
                            "type": "directory_pattern",
                            "context": ctx_type,
                            "file_count": count,
                        },
                        evidence=[f"ctx:{ctx_type}:{count}"],
                        confidence=confidence,
                        source="context_observation",
                        tags=[ctx_type, "project_context"],
                    )
                )

        return candidates
