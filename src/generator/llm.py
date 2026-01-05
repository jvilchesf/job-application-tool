"""
LLM-based resume and cover letter generator using OpenAI.
"""

from typing import Optional

from loguru import logger
from openai import AsyncOpenAI

from shared.config import Settings, get_settings
from generator.profile import ProfileLoader


class ResumeGenerator:
    """Generates tailored resumes using LLM."""

    def __init__(
        self,
        profile_loader: ProfileLoader,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.profile_loader = profile_loader
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value()
            )
        return self._client

    async def generate_resume(
        self,
        job_title: str,
        job_description: str,
        company: str,
        matched_keywords: list[str],
    ) -> str:
        """
        Generate a tailored resume for a specific job.

        Returns:
            Resume content in Markdown format
        """
        profile_context = self.profile_loader.to_context_string()

        prompt = f"""You are an expert resume writer. Create a tailored resume for the following job.

## Candidate Profile:
{profile_context}

## Target Job:
**Position:** {job_title}
**Company:** {company}
**Matched Keywords:** {', '.join(matched_keywords)}

## Job Description:
{job_description}

## Instructions:
1. Create a professional resume tailored to this specific job
2. Emphasize experiences and skills that match the job requirements
3. Include the matched keywords naturally where relevant
4. Use action verbs and quantify achievements where possible
5. Keep it concise (max 2 pages when printed)
6. Format in clean Markdown

Output ONLY the resume content in Markdown format, nothing else."""

        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert resume writer who creates tailored, ATS-friendly resumes.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=3000,
        )

        content = response.choices[0].message.content
        logger.info(f"Generated resume for {job_title} at {company}")
        return content.strip() if content else ""


class CoverLetterGenerator:
    """Generates tailored cover letters using LLM."""

    def __init__(
        self,
        profile_loader: ProfileLoader,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.profile_loader = profile_loader
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value()
            )
        return self._client

    async def generate_cover_letter(
        self,
        job_title: str,
        job_description: str,
        company: str,
        matched_keywords: list[str],
    ) -> str:
        """
        Generate a tailored cover letter for a specific job.

        Returns:
            Cover letter content in Markdown format
        """
        profile = self.profile_loader.profile
        profile_context = self.profile_loader.to_context_string()

        prompt = f"""You are an expert cover letter writer. Create a compelling cover letter for the following job.

## Candidate Profile:
{profile_context}

## Target Job:
**Position:** {job_title}
**Company:** {company}
**Matched Keywords:** {', '.join(matched_keywords)}

## Job Description:
{job_description}

## Instructions:
1. Write a professional, personalized cover letter
2. Show genuine interest in {company} specifically
3. Highlight 2-3 most relevant experiences that match the job
4. Reference the matched keywords naturally
5. Keep it concise (3-4 paragraphs)
6. Include a strong opening and call to action
7. Sign with the candidate's name: {profile.personal.name}

Output ONLY the cover letter content, nothing else."""

        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert cover letter writer who creates compelling, personalized letters.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1500,
        )

        content = response.choices[0].message.content
        logger.info(f"Generated cover letter for {job_title} at {company}")
        return content.strip() if content else ""
