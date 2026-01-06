"""
LLM-based job-CV matching using OpenAI.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import Settings, get_settings

from .cv_loader import CVLoader


@dataclass
class MatchResult:
    """Result of LLM matching."""

    score: int  # 1-5
    reasoning: str
    success: bool = True
    error: Optional[str] = None


SYSTEM_PROMPT = """You are an expert technical recruiter and hiring specialist with deep knowledge of cybersecurity, network engineering, and IT infrastructure roles. Your task is to evaluate how well a candidate's CV matches a specific job posting.

You must provide:
1. A match score from 1-5
2. A brief reasoning (2-3 sentences) explaining the score

Score Definitions:
- 1 (Poor): Minimal overlap. Different field or significantly misaligned experience.
- 2 (Weak): Some transferable skills but major gaps in required experience.
- 3 (Moderate): Reasonable fit with some matching skills but notable gaps.
- 4 (Good): Strong alignment with most requirements met, minor gaps acceptable.
- 5 (Excellent): Near-perfect match, candidate exceeds most requirements.

Consider:
- Years of experience alignment
- Technical skill overlap
- Certification relevance
- Industry experience
- Seniority level match
- Location/language requirements if specified

IMPORTANT: Respond ONLY with valid JSON in the exact format specified. No other text."""


class LLMMatcher:
    """Matches jobs against CV using LLM."""

    def __init__(
        self,
        cv_loader: CVLoader,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.cv_loader = cv_loader
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value()
            )
        return self._client

    async def match_job(
        self,
        job_title: str,
        company: str,
        location: str,
        job_description: str,
    ) -> MatchResult:
        """
        Match a job against the CV using LLM.

        Returns:
            MatchResult with score (1-5) and reasoning
        """
        cv_context = self.cv_loader.to_context_string()

        user_prompt = f"""## Candidate CV:
{cv_context}

## Job Posting:
**Title:** {job_title}
**Company:** {company}
**Location:** {location}

**Description:**
{job_description}

## Task:
Evaluate how well this candidate matches the job requirements.
Respond in the following JSON format only:

{{"score": <1-5>, "reasoning": "<2-3 sentence explanation>"}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model_mini,  # Use mini model for cost efficiency
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,  # Lower temperature for more consistent scoring
                max_tokens=500,
                response_format={"type": "json_object"},  # Force JSON response
            )

            content = response.choices[0].message.content
            if not content:
                return MatchResult(
                    score=0,
                    reasoning="",
                    success=False,
                    error="Empty response from LLM",
                )

            # Parse JSON response
            result = json.loads(content)
            score = int(result.get("score", 0))
            reasoning = result.get("reasoning", "")

            # Validate score range
            if not 1 <= score <= 5:
                logger.warning(f"Invalid score {score}, clamping to range 1-5")
                score = max(1, min(5, score))

            logger.info(f"Matched {job_title} at {company}: score={score}")
            return MatchResult(score=score, reasoning=reasoning)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return MatchResult(
                score=0,
                reasoning="",
                success=False,
                error=f"JSON parse error: {e}",
            )
        except Exception as e:
            logger.error(f"LLM matching failed: {e}")
            return MatchResult(
                score=0,
                reasoning="",
                success=False,
                error=str(e),
            )
