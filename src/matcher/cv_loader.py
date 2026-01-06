"""
CV loader for the Match Service.
Loads candidate CV from YAML for LLM matching context.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger


@dataclass
class CertificationInfo:
    """Certification entry."""

    name: str = ""
    issuer: str = ""
    date: str = ""
    credential_id: str = ""


@dataclass
class ExperienceEntry:
    """Work experience entry."""

    company: str = ""
    title: str = ""
    employment_type: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    duration: str = ""
    achievements: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    project_highlights: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)


@dataclass
class CVData:
    """Complete CV data structure."""

    name: str = ""
    headline: str = ""
    location: str = ""
    languages: list[dict] = field(default_factory=list)
    summary: str = ""
    core_competencies: list[str] = field(default_factory=list)
    technical_skills: dict[str, list[str]] = field(default_factory=dict)
    certifications: list[CertificationInfo] = field(default_factory=list)
    experience: list[ExperienceEntry] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)
    matching_hints: dict[str, list[str]] = field(default_factory=dict)


class CVLoader:
    """Loads and manages CV data for LLM matching."""

    def __init__(self, cv_path: Optional[Path] = None):
        self.cv_path = cv_path
        self._cv_data: Optional[CVData] = None

    def load(self, path: Optional[Path] = None) -> CVData:
        """Load CV from YAML file. Supports both legacy and RenderCV formats."""
        path = path or self.cv_path
        if not path:
            raise ValueError("No CV path specified")

        if not path.exists():
            raise FileNotFoundError(f"CV file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        # Detect format: RenderCV uses "cv" as root key
        if "cv" in data:
            return self._load_rendercv_format(data)

        # Parse personal info (legacy format)
        personal = data.get("personal", {})

        # Parse certifications
        certifications = [
            CertificationInfo(
                name=cert.get("name", ""),
                issuer=cert.get("issuer", ""),
                date=cert.get("date", ""),
                credential_id=cert.get("credential_id", ""),
            )
            for cert in data.get("certifications", [])
        ]

        # Parse experience
        experience = [
            ExperienceEntry(
                company=exp.get("company", ""),
                title=exp.get("title", ""),
                employment_type=exp.get("employment_type", ""),
                location=exp.get("location", ""),
                start_date=exp.get("start_date", ""),
                end_date=exp.get("end_date", ""),
                duration=exp.get("duration", ""),
                achievements=exp.get("achievements", []),
                responsibilities=exp.get("responsibilities", []),
                project_highlights=exp.get("project_highlights", []),
                technologies=exp.get("technologies", []),
            )
            for exp in data.get("experience", [])
        ]

        self._cv_data = CVData(
            name=personal.get("name", ""),
            headline=personal.get("headline", ""),
            location=personal.get("location", ""),
            languages=personal.get("languages", []),
            summary=data.get("summary", ""),
            core_competencies=data.get("core_competencies", []),
            technical_skills=data.get("technical_skills", {}),
            certifications=certifications,
            experience=experience,
            education=data.get("education", []),
            matching_hints=data.get("matching_hints", {}),
        )

        logger.info(f"Loaded CV for: {self._cv_data.name}")
        return self._cv_data

    def _load_rendercv_format(self, data: dict) -> CVData:
        """Load CV from RenderCV YAML format."""
        cv = data.get("cv", {})
        sections = cv.get("sections", {})

        # Parse certifications from RenderCV format
        certifications = [
            CertificationInfo(
                name=cert.get("label", ""),
                issuer=cert.get("details", "").split(",")[0] if cert.get("details") else "",
                date=cert.get("details", "").split(",")[-1].strip() if cert.get("details") else "",
            )
            for cert in sections.get("certifications", [])
        ]

        # Parse experience from RenderCV format
        experience = [
            ExperienceEntry(
                company=exp.get("company", ""),
                title=exp.get("position", ""),
                location=exp.get("location", ""),
                start_date=str(exp.get("start_date", "")),
                end_date=str(exp.get("end_date", "")),
                achievements=exp.get("highlights", []),
            )
            for exp in sections.get("experience", [])
        ]

        # Parse skills into technical_skills dict
        technical_skills = {}
        for skill in sections.get("skills", []):
            label = skill.get("label", "").lower().replace(" ", "_")
            details = skill.get("details", "")
            if details:
                technical_skills[label] = [s.strip() for s in details.split(",")]

        # Parse summary
        summary_list = sections.get("summary", [])
        summary = summary_list[0] if summary_list else ""

        # Parse education
        education = [
            {
                "degree": edu.get("degree", edu.get("area", "")),
                "institution": edu.get("institution", ""),
                "location": edu.get("location", ""),
                "years": f"{edu.get('start_date', '')} - {edu.get('end_date', '')}",
            }
            for edu in sections.get("education", [])
        ]

        # Parse languages
        languages = [
            {"language": lang.get("label", ""), "proficiency": lang.get("details", "")}
            for lang in sections.get("languages", [])
        ]

        self._cv_data = CVData(
            name=cv.get("name", ""),
            headline=cv.get("label", ""),  # RenderCV uses 'label' for headline
            location=cv.get("location", ""),
            languages=languages,
            summary=summary,
            technical_skills=technical_skills,
            certifications=certifications,
            experience=experience,
            education=education,
        )

        logger.info(f"Loaded CV (RenderCV format) for: {self._cv_data.name}")
        return self._cv_data

    @property
    def cv_data(self) -> CVData:
        """Get loaded CV data."""
        if self._cv_data is None:
            self._cv_data = self.load()
        return self._cv_data

    def to_context_string(self) -> str:
        """Convert CV to string for LLM context."""
        cv = self.cv_data
        sections = []

        # Header
        sections.append(f"# {cv.name}")
        sections.append(f"**{cv.headline}**")
        sections.append(f"Location: {cv.location}")

        # Languages
        if cv.languages:
            langs = [f"{lang['language']} ({lang['proficiency']})" for lang in cv.languages]
            sections.append(f"Languages: {', '.join(langs)}")

        # Summary
        if cv.summary:
            sections.append(f"\n## Professional Summary\n{cv.summary.strip()}")

        # Core Competencies
        if cv.core_competencies:
            sections.append("\n## Core Competencies")
            sections.append(", ".join(cv.core_competencies))

        # Technical Skills
        if cv.technical_skills:
            sections.append("\n## Technical Skills")
            for category, skills in cv.technical_skills.items():
                category_name = category.replace("_", " ").title()
                sections.append(f"**{category_name}:** {', '.join(skills)}")

        # Certifications
        if cv.certifications:
            sections.append("\n## Certifications")
            for cert in cv.certifications:
                cert_line = f"- {cert.name} ({cert.issuer})"
                if cert.date:
                    cert_line += f" - {cert.date}"
                sections.append(cert_line)

        # Experience
        if cv.experience:
            sections.append("\n## Professional Experience")
            for exp in cv.experience:
                sections.append(f"\n### {exp.title} at {exp.company}")
                if exp.location:
                    sections.append(f"Location: {exp.location}")
                if exp.duration:
                    sections.append(f"Duration: {exp.duration}")
                elif exp.start_date:
                    sections.append(f"Period: {exp.start_date} - {exp.end_date}")

                if exp.achievements:
                    sections.append("**Achievements:**")
                    for achievement in exp.achievements:
                        sections.append(f"- {achievement}")

                if exp.responsibilities:
                    sections.append("**Responsibilities:**")
                    for resp in exp.responsibilities:
                        sections.append(f"- {resp}")

                if exp.project_highlights:
                    sections.append("**Project Highlights:**")
                    for highlight in exp.project_highlights:
                        sections.append(f"- {highlight}")

                if exp.technologies:
                    sections.append(f"**Technologies:** {', '.join(exp.technologies)}")

        # Education
        if cv.education:
            sections.append("\n## Education")
            for edu in cv.education:
                edu_line = f"- {edu.get('degree', '')} - {edu.get('institution', '')}"
                if edu.get("location"):
                    edu_line += f", {edu['location']}"
                if edu.get("years"):
                    edu_line += f" ({edu['years']})"
                sections.append(edu_line)

        return "\n".join(sections)
