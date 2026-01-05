"""
Template-based job scoring system.
Loads scoring templates from YAML and matches jobs against keywords.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger


@dataclass
class ScoringTemplate:
    """A scoring template with trigger and support keywords."""

    name: str
    trigger_keywords: list[str] = field(default_factory=list)
    support_keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    trigger_weight: int = 10
    support_weight: int = 4
    negative_weight: int = -15


@dataclass
class ScoringConfig:
    """Global scoring configuration."""

    min_score: int = 30
    min_triggers: int = 2
    title_bonus_multiplier: float = 1.5


@dataclass
class ScoringResult:
    """Result of scoring a job."""

    score: int
    matched_triggers: list[str]
    matched_support: list[str]
    matched_negative: list[str]
    passed: bool
    template_name: str


class TemplateMatcher:
    """Matches jobs against scoring templates."""

    def __init__(self, templates_path: Optional[Path] = None):
        self.templates: list[ScoringTemplate] = []
        self.config = ScoringConfig()

        if templates_path:
            self.load_templates(templates_path)

    def load_templates(self, path: Path) -> None:
        """Load templates from YAML file."""
        if not path.exists():
            logger.warning(f"Templates file not found: {path}")
            return

        with open(path) as f:
            data = yaml.safe_load(f)

        # Load global config
        if "scoring" in data:
            scoring = data["scoring"]
            self.config = ScoringConfig(
                min_score=scoring.get("min_score", 30),
                min_triggers=scoring.get("min_triggers", 2),
                title_bonus_multiplier=scoring.get("title_bonus_multiplier", 1.5),
            )

        # Load templates
        self.templates = []
        for name, template_data in data.get("templates", {}).items():
            template = ScoringTemplate(
                name=name,
                trigger_keywords=template_data.get("trigger_keywords", []),
                support_keywords=template_data.get("support_keywords", []),
                negative_keywords=template_data.get("negative_keywords", []),
                trigger_weight=template_data.get("trigger_weight", 10),
                support_weight=template_data.get("support_weight", 4),
                negative_weight=template_data.get("negative_weight", -15),
            )
            self.templates.append(template)

        logger.info(f"Loaded {len(self.templates)} scoring templates")

    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching."""
        return text.lower().strip()

    def _find_matches(
        self, text: str, keywords: list[str], is_title: bool = False
    ) -> tuple[list[str], int]:
        """
        Find keyword matches in text.

        Returns:
            Tuple of (matched keywords, total weighted score)
        """
        text_lower = self._normalize_text(text)
        matched = []
        score = 0

        for keyword in keywords:
            keyword_lower = self._normalize_text(keyword)

            # Use word boundary matching for more accurate results
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            if re.search(pattern, text_lower):
                matched.append(keyword)
                # Title matches get bonus
                weight = 1.5 if is_title else 1.0
                score += weight

        return matched, score

    def score_job(
        self,
        title: str,
        description: str,
        template_name: Optional[str] = None,
    ) -> ScoringResult:
        """
        Score a job against templates.

        Args:
            title: Job title
            description: Job description
            template_name: Specific template to use (uses all if None)

        Returns:
            ScoringResult with score and matches
        """
        combined_text = f"{title}\n{description}"
        best_result: Optional[ScoringResult] = None

        templates_to_check = self.templates
        if template_name:
            templates_to_check = [t for t in self.templates if t.name == template_name]

        for template in templates_to_check:
            # Match triggers
            title_triggers, title_trigger_score = self._find_matches(
                title, template.trigger_keywords, is_title=True
            )
            desc_triggers, desc_trigger_score = self._find_matches(
                description, template.trigger_keywords, is_title=False
            )
            all_triggers = list(set(title_triggers + desc_triggers))
            trigger_score = (len(all_triggers)) * template.trigger_weight

            # Add title bonus
            trigger_score += int(len(title_triggers) * template.trigger_weight * 0.5)

            # Match support keywords
            title_support, _ = self._find_matches(
                title, template.support_keywords, is_title=True
            )
            desc_support, _ = self._find_matches(
                description, template.support_keywords, is_title=False
            )
            all_support = list(set(title_support + desc_support))
            support_score = len(all_support) * template.support_weight

            # Match negative keywords
            all_negative, _ = self._find_matches(
                combined_text, template.negative_keywords
            )
            negative_score = len(all_negative) * template.negative_weight

            # Calculate total
            total_score = trigger_score + support_score + negative_score
            total_score = max(0, total_score)  # Don't go negative

            # Check if passed
            passed = (
                len(all_triggers) >= self.config.min_triggers
                and total_score >= self.config.min_score
            )

            result = ScoringResult(
                score=total_score,
                matched_triggers=all_triggers,
                matched_support=all_support,
                matched_negative=all_negative,
                passed=passed,
                template_name=template.name,
            )

            # Keep best result
            if best_result is None or result.score > best_result.score:
                best_result = result

        if best_result is None:
            return ScoringResult(
                score=0,
                matched_triggers=[],
                matched_support=[],
                matched_negative=[],
                passed=False,
                template_name="none",
            )

        return best_result
