"""
CV Tailoring using LLM.
Uses OpenAI to customize CV content for specific job descriptions.
"""

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml
from loguru import logger
from openai import AsyncOpenAI

from shared.config import Settings, get_settings


@dataclass
class TailoringResult:
    """Result of CV tailoring."""
    success: bool
    tailored_cv: dict[str, Any]
    cover_letter: str
    ats_keywords: list[str]
    error: Optional[str] = None


class CVTailor:
    """Uses LLM to tailor CV content for specific jobs."""

    def __init__(
        self,
        base_cv_path: Path,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.base_cv_path = base_cv_path
        self._client: Optional[AsyncOpenAI] = None
        self._base_cv: Optional[dict] = None

    @property
    def client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value()
            )
        return self._client

    def load_base_cv(self) -> dict[str, Any]:
        """Load base CV from YAML file."""
        if self._base_cv is None:
            with open(self.base_cv_path, "r") as f:
                self._base_cv = yaml.safe_load(f)
        return self._base_cv

    def _extract_json_array(self, text: str) -> list[str]:
        """Extract JSON array from text, handling markdown code blocks."""
        if not text:
            return []

        # Remove markdown code blocks if present
        text = text.strip()
        if text.startswith("```"):
            # Remove opening ```json or ```
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Try to find JSON array in the text
        import re
        # Look for array pattern
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            text = match.group(0)

        return json.loads(text)

    async def extract_ats_keywords(
        self,
        job_title: str,
        job_description: str,
    ) -> list[str]:
        """
        Extract ATS keywords from job description.
        Uses the prompt pattern from the user's tips.
        """
        # Handle empty job description
        if not job_description or len(job_description.strip()) < 50:
            logger.warning(f"Job description too short for ATS extraction: {len(job_description or '')} chars")
            return []

        prompt = f"""Act as an ATS + recruiter. Extract the top 25 technical skills and keywords from this job description that a candidate's CV should contain.

Job Title: {job_title}

Job Description:
{job_description[:4000]}

IMPORTANT RULES:
1. Output all keywords in ENGLISH (translate if needed)
2. Focus on TECHNICAL SKILLS and TOOLS (e.g., "ISO 27001", "NIST", "SIEM", "Azure", "Firewall", "Python")
3. Include security frameworks, certifications, tools, and platforms mentioned
4. Include soft skills only if explicitly required (e.g., "Leadership", "Communication")
5. Do NOT include job titles (e.g., "Security Manager") - only skills
6. Do NOT include generic terms like "Experience" or "Professional"

Output ONLY a JSON array of keywords, nothing else. Example: ["ISO 27001", "NIST 800-53", "SIEM", "Incident Response", "Risk Assessment", "Azure", "Leadership"]"""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model_mini,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert ATS analyst. Output only valid JSON arrays, no markdown formatting.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            content = response.choices[0].message.content
            if not content:
                logger.warning("Empty response from OpenAI for ATS keywords")
                return []

            # Parse JSON array (handles markdown code blocks)
            keywords = self._extract_json_array(content.strip())

            if not isinstance(keywords, list):
                logger.warning(f"ATS keywords response is not a list: {type(keywords)}")
                return []

            logger.info(f"Extracted {len(keywords)} ATS keywords: {keywords[:5]}...")
            return keywords

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ATS keywords JSON: {e}. Raw content: {content[:200] if content else 'None'}")
            return []
        except Exception as e:
            logger.error(f"Failed to extract ATS keywords: {e}")
            return []

    def _score_text_relevance(self, text: str, keywords: list[str]) -> int:
        """Score how many keywords appear in the text (case-insensitive)."""
        if not text or not keywords:
            return 0
        text_lower = text.lower()
        return sum(1 for kw in keywords if kw.lower() in text_lower)

    def _reorder_by_relevance(
        self, items: list[dict], keywords: list[str], text_key: str = "highlights"
    ) -> list[dict]:
        """Reorder items by keyword relevance."""
        if not items or not keywords:
            return items

        def get_score(item: dict) -> int:
            score = 0
            # Score from highlights/details
            if text_key in item:
                if isinstance(item[text_key], list):
                    for h in item[text_key]:
                        score += self._score_text_relevance(str(h), keywords)
                else:
                    score += self._score_text_relevance(str(item[text_key]), keywords)
            # Score from position/label
            if "position" in item:
                score += self._score_text_relevance(item["position"], keywords) * 2
            if "label" in item:
                score += self._score_text_relevance(item["label"], keywords) * 2
            if "details" in item and isinstance(item["details"], str):
                score += self._score_text_relevance(item["details"], keywords)
            return score

        return sorted(items, key=get_score, reverse=True)

    def _reorder_highlights(self, highlights: list[str], keywords: list[str]) -> list[str]:
        """Reorder highlights to put keyword-matching ones first."""
        if not highlights or not keywords:
            return highlights

        scored = [(h, self._score_text_relevance(h, keywords)) for h in highlights]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [h for h, _ in scored]

    def _create_key_skills_section(
        self, ats_keywords: list[str], cv_sections: dict
    ) -> list[dict]:
        """Create a Key Skills section with matching ATS keywords.

        Checks skills, certifications, and experience highlights for matches.
        """
        # Collect all text from skills, certifications, and experience
        all_text = ""
        all_terms = []

        # From skills section
        for skill in cv_sections.get("skills", []):
            if "details" in skill:
                all_text += " " + skill["details"].lower()
                for term in skill["details"].replace("(", ",").replace(")", ",").split(","):
                    term = term.strip()
                    if len(term) > 2:
                        all_terms.append(term.lower())
            if "label" in skill:
                all_text += " " + skill["label"].lower()
                all_terms.append(skill["label"].lower())

        # From certifications section
        for cert in cv_sections.get("certifications", []):
            if "label" in cert:
                all_text += " " + cert["label"].lower()
                # Extract acronyms like CISM, CRISC, CEH
                for word in cert["label"].split():
                    if word.isupper() and len(word) >= 2:
                        all_terms.append(word.lower())
                    elif word.startswith("(") and word.endswith(")"):
                        all_terms.append(word[1:-1].lower())

        # From experience highlights (key technical terms)
        for exp in cv_sections.get("experience", []):
            for highlight in exp.get("highlights", []):
                all_text += " " + highlight.lower()

        # Find ATS keywords that match candidate's profile
        matching_keywords = []
        for kw in ats_keywords:
            kw_lower = kw.lower()
            # Check if keyword exists in all text
            if kw_lower in all_text:
                matching_keywords.append(kw)
            # Check if keyword matches any specific term
            elif any(kw_lower == term or kw_lower in term or term in kw_lower for term in all_terms if len(term) > 2):
                matching_keywords.append(kw)

        if not matching_keywords:
            return []

        # Return as a single entry with comma-separated skills
        return [{"label": "Key Skills", "details": ", ".join(matching_keywords[:12])}]

    async def tailor_cv(
        self,
        job_title: str,
        company: str,
        job_description: str,
        ats_keywords: list[str],
    ) -> dict[str, Any]:
        """
        Tailor CV content for a specific job.
        - Rewrites summary with ATS keywords
        - Reorders experience highlights by relevance
        - Reorders skills by relevance
        - Adds Key Skills section with matching ATS keywords
        """
        base_cv = copy.deepcopy(self.load_base_cv())
        cv_content = base_cv.get("cv", {})
        sections = cv_content.get("sections", {})

        # =====================================================================
        # 1. Reorder experience highlights by keyword relevance
        # =====================================================================
        experience = sections.get("experience", [])
        for exp in experience:
            if "highlights" in exp:
                exp["highlights"] = self._reorder_highlights(
                    exp["highlights"], ats_keywords
                )
        # Also reorder experiences themselves (most relevant job first)
        sections["experience"] = self._reorder_by_relevance(
            experience, ats_keywords, "highlights"
        )
        logger.debug(f"Reordered {len(experience)} experience entries by relevance")

        # =====================================================================
        # 2. Reorder skills by keyword relevance
        # =====================================================================
        skills = sections.get("skills", [])
        sections["skills"] = self._reorder_by_relevance(skills, ats_keywords, "details")
        logger.debug(f"Reordered {len(skills)} skill entries by relevance")

        # =====================================================================
        # 3. Create Key Skills section from matching ATS keywords
        # =====================================================================
        key_skills = self._create_key_skills_section(ats_keywords, sections)
        if key_skills:
            # Insert key_skills right after summary
            new_sections = {}
            for key, value in sections.items():
                new_sections[key] = value
                if key == "summary":
                    new_sections["key_skills"] = key_skills
            sections = new_sections
            logger.debug(f"Added Key Skills section with {len(key_skills[0]['details'].split(', '))} skills")

        # =====================================================================
        # 4. Tailor summary using LLM
        # =====================================================================
        current_summary = sections.get("summary", [""])[0] if sections.get("summary") else ""

        # Get experience highlights for context
        experience_context = ""
        for exp in sections.get("experience", [])[:3]:
            experience_context += f"\n{exp.get('position', '')} at {exp.get('company', '')}:\n"
            for h in exp.get("highlights", [])[:3]:
                experience_context += f"  - {h}\n"

        prompt = f"""You are a senior recruiter. Rewrite the CV summary to match this job while staying truthful.

Target Job: {job_title} at {company}

Job Description:
{job_description[:3000]}

ATS Keywords to incorporate naturally: {', '.join(ats_keywords[:15])}

Current Summary:
{current_summary}

Relevant Experience:
{experience_context}

Rules:
- Keep summary to 2-3 sentences
- Emphasize relevant skills and experience
- Incorporate ATS keywords naturally
- Stay truthful - don't invent experience
- Make it compelling and specific to this role

Output ONLY the new summary text, nothing else."""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model_mini,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert resume writer. Output only the summary text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=300,
            )

            new_summary = response.choices[0].message.content.strip()
            # Remove quotes if present
            if new_summary.startswith('"') and new_summary.endswith('"'):
                new_summary = new_summary[1:-1]

            # Update the CV with tailored summary
            sections["summary"] = [new_summary]
            base_cv["cv"]["sections"] = sections

            logger.info(f"Tailored CV for {job_title} at {company} (summary + reordering + key skills)")
            return base_cv

        except Exception as e:
            logger.error(f"Failed to tailor CV: {e}")
            # Still return CV with reordered sections even if summary fails
            base_cv["cv"]["sections"] = sections
            return base_cv

    async def _detect_language(self, text: str) -> tuple[str, str]:
        """
        Detect the language of the text.
        Returns (language_code, language_name) e.g., ("de", "German")
        """
        # Quick heuristic detection based on common words
        text_lower = text.lower()

        # German indicators
        german_words = ["und", "der", "die", "das", "für", "mit", "wir", "sie", "sind", "haben", "werden", "ihre", "unser", "arbeit", "erfahrung", "kenntnisse", "aufgaben", "anforderungen"]
        german_count = sum(1 for word in german_words if f" {word} " in f" {text_lower} ")

        # French indicators
        french_words = ["et", "le", "la", "les", "pour", "avec", "nous", "vous", "sont", "avoir", "être", "notre", "votre", "travail", "expérience", "compétences", "missions", "profil"]
        french_count = sum(1 for word in french_words if f" {word} " in f" {text_lower} ")

        # Italian indicators
        italian_words = ["e", "il", "la", "per", "con", "noi", "loro", "sono", "avere", "essere", "nostro", "lavoro", "esperienza", "competenze", "requisiti"]
        italian_count = sum(1 for word in italian_words if f" {word} " in f" {text_lower} ")

        # Determine language
        if german_count >= 5:
            return ("de", "German")
        elif french_count >= 5:
            return ("fr", "French")
        elif italian_count >= 4:
            return ("it", "Italian")
        else:
            return ("en", "English")

    async def generate_cover_letter(
        self,
        job_title: str,
        company: str,
        location: str,
        job_description: str,
        ats_keywords: list[str],
    ) -> str:
        """
        Generate a cover letter for the job.
        Uses the prompt pattern from the user's tips.
        Detects job language and adds language learning note if not English.
        """
        base_cv = self.load_base_cv()
        cv_content = base_cv.get("cv", {})
        name = cv_content.get("name", "")
        sections = cv_content.get("sections", {})

        # Detect job posting language
        lang_code, lang_name = await self._detect_language(job_description)
        language_note = ""
        if lang_code != "en":
            language_note = f"""
IMPORTANT: The job posting is in {lang_name}.
- Write the cover letter in ENGLISH (not {lang_name})
- Include a sentence mentioning that the candidate is 100% committed to learning {lang_name} and is already taking steps to become proficient
- The candidate already speaks English and Spanish fluently"""
            logger.info(f"Job posting detected as {lang_name} - will add language learning note")

        # Build resume context
        summary = sections.get("summary", [""])[0] if sections.get("summary") else ""

        experience_context = ""
        for exp in sections.get("experience", [])[:2]:
            experience_context += f"\n**{exp.get('position', '')}** at {exp.get('company', '')} ({exp.get('start_date', '')} - {exp.get('end_date', '')}):\n"
            for h in exp.get("highlights", [])[:3]:
                experience_context += f"- {h}\n"

        prompt = f"""Write a concise cover letter (180-220 words) that sounds human, not generic.

Structure: hook → 2 proof paragraphs → close with a call to action

Job Title: {job_title}
Company: {company}
Location: {location}

Job Description:
{job_description}

Candidate Name: {name}

Candidate Summary:
{summary}

Key Experience:
{experience_context}

ATS Keywords to incorporate: {', '.join(ats_keywords[:10])}
{language_note}

Rules:
- Use 2 specific achievements from the experience
- Mirror keywords from the job description
- Sound human and enthusiastic, not robotic
- End with candidate's name as signature
- Do NOT include date, address headers, or "Dear Hiring Manager" - start directly with the hook

Output ONLY the cover letter text, nothing else."""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,  # Use better model for cover letter
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert cover letter writer who creates compelling, personalized letters.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            cover_letter = response.choices[0].message.content.strip()
            logger.info(f"Generated cover letter for {job_title} at {company}")
            return cover_letter

        except Exception as e:
            logger.error(f"Failed to generate cover letter: {e}")
            return ""

    async def tailor_for_job(
        self,
        job_title: str,
        company: str,
        location: str,
        job_description: str,
    ) -> TailoringResult:
        """
        Complete tailoring pipeline for a job.
        Returns tailored CV, cover letter, and ATS keywords.
        """
        try:
            # Step 1: Extract ATS keywords
            logger.debug(f"Extracting ATS keywords for {job_title}")
            ats_keywords = await self.extract_ats_keywords(job_title, job_description)

            # Step 2: Tailor CV
            logger.debug(f"Tailoring CV for {job_title}")
            tailored_cv = await self.tailor_cv(
                job_title=job_title,
                company=company,
                job_description=job_description,
                ats_keywords=ats_keywords,
            )

            # Step 3: Generate cover letter
            logger.debug(f"Generating cover letter for {job_title}")
            cover_letter = await self.generate_cover_letter(
                job_title=job_title,
                company=company,
                location=location,
                job_description=job_description,
                ats_keywords=ats_keywords,
            )

            return TailoringResult(
                success=True,
                tailored_cv=tailored_cv,
                cover_letter=cover_letter,
                ats_keywords=ats_keywords,
            )

        except Exception as e:
            logger.error(f"Tailoring failed for {job_title} at {company}: {e}")
            return TailoringResult(
                success=False,
                tailored_cv={},
                cover_letter="",
                ats_keywords=[],
                error=str(e),
            )
