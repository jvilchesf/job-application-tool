"""
User profile loader and manager.
Loads professional profile from YAML for CV generation.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger


@dataclass
class PersonalInfo:
    """Personal contact information."""

    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""


@dataclass
class WorkExperience:
    """Work experience entry."""

    company: str = ""
    title: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    achievements: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)


@dataclass
class Education:
    """Education entry."""

    institution: str = ""
    degree: str = ""
    field: str = ""
    location: str = ""
    graduation_date: str = ""
    gpa: str = ""
    achievements: list[str] = field(default_factory=list)


@dataclass
class Certification:
    """Certification entry."""

    name: str = ""
    issuer: str = ""
    date: str = ""
    expiry: str = ""
    credential_id: str = ""


@dataclass
class UserProfile:
    """Complete user profile for CV generation."""

    personal: PersonalInfo = field(default_factory=PersonalInfo)
    summary: str = ""
    experience: list[WorkExperience] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    certifications: list[Certification] = field(default_factory=list)
    skills: dict[str, list[str]] = field(default_factory=dict)
    languages: dict[str, str] = field(default_factory=dict)
    interests: list[str] = field(default_factory=list)


class ProfileLoader:
    """Loads and manages user profile."""

    def __init__(self, profile_path: Optional[Path] = None):
        self.profile_path = profile_path
        self._profile: Optional[UserProfile] = None

    def load(self, path: Optional[Path] = None) -> UserProfile:
        """Load profile from YAML file."""
        path = path or self.profile_path
        if not path:
            raise ValueError("No profile path specified")

        if not path.exists():
            logger.warning(f"Profile file not found: {path}")
            return UserProfile()

        with open(path) as f:
            data = yaml.safe_load(f)

        # Parse personal info
        personal_data = data.get("personal", {})
        personal = PersonalInfo(
            name=personal_data.get("name", ""),
            email=personal_data.get("email", ""),
            phone=personal_data.get("phone", ""),
            location=personal_data.get("location", ""),
            linkedin=personal_data.get("linkedin", ""),
            github=personal_data.get("github", ""),
            website=personal_data.get("website", ""),
        )

        # Parse experience
        experience = []
        for exp_data in data.get("experience", []):
            exp = WorkExperience(
                company=exp_data.get("company", ""),
                title=exp_data.get("title", ""),
                location=exp_data.get("location", ""),
                start_date=exp_data.get("start_date", ""),
                end_date=exp_data.get("end_date", ""),
                description=exp_data.get("description", ""),
                achievements=exp_data.get("achievements", []),
                technologies=exp_data.get("technologies", []),
            )
            experience.append(exp)

        # Parse education
        education = []
        for edu_data in data.get("education", []):
            edu = Education(
                institution=edu_data.get("institution", ""),
                degree=edu_data.get("degree", ""),
                field=edu_data.get("field", ""),
                location=edu_data.get("location", ""),
                graduation_date=edu_data.get("graduation_date", ""),
                gpa=edu_data.get("gpa", ""),
                achievements=edu_data.get("achievements", []),
            )
            education.append(edu)

        # Parse certifications
        certifications = []
        for cert_data in data.get("certifications", []):
            cert = Certification(
                name=cert_data.get("name", ""),
                issuer=cert_data.get("issuer", ""),
                date=cert_data.get("date", ""),
                expiry=cert_data.get("expiry", ""),
                credential_id=cert_data.get("credential_id", ""),
            )
            certifications.append(cert)

        self._profile = UserProfile(
            personal=personal,
            summary=data.get("summary", ""),
            experience=experience,
            education=education,
            certifications=certifications,
            skills=data.get("skills", {}),
            languages=data.get("languages", {}),
            interests=data.get("interests", []),
        )

        logger.info(f"Loaded profile for: {personal.name}")
        return self._profile

    @property
    def profile(self) -> UserProfile:
        """Get loaded profile."""
        if self._profile is None:
            self._profile = self.load()
        return self._profile

    def to_context_string(self) -> str:
        """Convert profile to string for LLM context."""
        p = self.profile

        sections = []

        # Personal info
        sections.append(f"# {p.personal.name}")
        sections.append(f"Email: {p.personal.email}")
        sections.append(f"Phone: {p.personal.phone}")
        sections.append(f"Location: {p.personal.location}")
        if p.personal.linkedin:
            sections.append(f"LinkedIn: {p.personal.linkedin}")
        if p.personal.github:
            sections.append(f"GitHub: {p.personal.github}")

        # Summary
        if p.summary:
            sections.append(f"\n## Professional Summary\n{p.summary}")

        # Experience
        if p.experience:
            sections.append("\n## Work Experience")
            for exp in p.experience:
                sections.append(f"\n### {exp.title} at {exp.company}")
                sections.append(f"{exp.location} | {exp.start_date} - {exp.end_date}")
                if exp.description:
                    sections.append(exp.description)
                if exp.achievements:
                    sections.append("Achievements:")
                    for ach in exp.achievements:
                        sections.append(f"- {ach}")
                if exp.technologies:
                    sections.append(f"Technologies: {', '.join(exp.technologies)}")

        # Education
        if p.education:
            sections.append("\n## Education")
            for edu in p.education:
                sections.append(f"\n### {edu.degree} in {edu.field}")
                sections.append(f"{edu.institution}, {edu.location}")
                sections.append(f"Graduated: {edu.graduation_date}")

        # Certifications
        if p.certifications:
            sections.append("\n## Certifications")
            for cert in p.certifications:
                sections.append(f"- {cert.name} ({cert.issuer}, {cert.date})")

        # Skills
        if p.skills:
            sections.append("\n## Skills")
            for category, skills in p.skills.items():
                sections.append(f"**{category}:** {', '.join(skills)}")

        # Languages
        if p.languages:
            sections.append("\n## Languages")
            for lang, level in p.languages.items():
                sections.append(f"- {lang}: {level}")

        return "\n".join(sections)
