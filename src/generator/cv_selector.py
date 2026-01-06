"""
CV Selector - Chooses the best CV variant based on job requirements.
"""

from pathlib import Path
from typing import Optional

from loguru import logger


# CV variants and their matching keywords
CV_VARIANTS = {
    "ciso": {
        "path": "ernest_haberli_ciso.yaml",
        "keywords": [
            # Executive/Leadership titles
            "ciso", "chief information security", "chief security officer",
            "head of security", "head of it security", "head of information security",
            "security director", "director of security", "it security director",
            "security manager", "it security manager", "information security manager",
            "vp security", "vice president security",
            # Strategic keywords
            "security strategy", "security governance", "security leadership",
            "isms", "information security management", "security program",
            "executive", "board", "c-level", "strategic",
            "iso 27001", "compliance officer", "data protection officer", "dpo",
            "grc", "governance risk compliance",
        ],
        "weight": 1.0,  # Default weight
    },
    "vuln": {
        "path": "ernest_haberli_vuln.yaml",
        "keywords": [
            # Technical titles
            "security engineer", "security analyst", "security specialist",
            "vulnerability", "vuln management", "vulnerability analyst",
            "soc analyst", "security operations", "soc engineer",
            "penetration tester", "pen tester", "ethical hacker",
            "security architect", "cloud security engineer",
            # Technical keywords
            "siem", "splunk", "qradar", "sentinel",
            "nessus", "qualys", "rapid7", "nexpose", "tenable",
            "vulnerability scanning", "vulnerability assessment",
            "patch management", "remediation", "hardening",
            "cis benchmark", "baseline", "compliance monitoring",
            "incident response", "threat detection", "threat hunting",
            "azure security", "aws security", "cloud security",
            "windows server", "linux", "network security",
        ],
        "weight": 1.0,
    },
}


def select_best_cv(
    job_title: str,
    job_description: str,
    cv_dir: Path,
) -> tuple[Path, str]:
    """
    Select the best CV variant based on job title and description.

    Args:
        job_title: The job title
        job_description: The job description
        cv_dir: Directory containing CV templates

    Returns:
        Tuple of (cv_path, cv_variant_name)
    """
    # Combine title and description for matching
    text = f"{job_title} {job_description}".lower()

    scores = {}

    for variant_name, variant_config in CV_VARIANTS.items():
        score = 0
        matched_keywords = []

        for keyword in variant_config["keywords"]:
            if keyword.lower() in text:
                # Title matches worth more
                if keyword.lower() in job_title.lower():
                    score += 3
                else:
                    score += 1
                matched_keywords.append(keyword)

        # Apply weight
        score *= variant_config["weight"]
        scores[variant_name] = (score, matched_keywords)

        logger.debug(
            f"CV '{variant_name}' score: {score} "
            f"(matched: {matched_keywords[:5]}{'...' if len(matched_keywords) > 5 else ''})"
        )

    # Select the variant with highest score
    best_variant = max(scores.keys(), key=lambda k: scores[k][0])
    best_score, best_keywords = scores[best_variant]

    # If no good match, default to CISO (more general)
    if best_score == 0:
        best_variant = "ciso"
        logger.info(f"No keyword matches, defaulting to CISO CV")
    else:
        logger.info(
            f"Selected '{best_variant}' CV (score: {best_score}, "
            f"keywords: {best_keywords[:3]}...)"
        )

    cv_path = cv_dir / CV_VARIANTS[best_variant]["path"]

    return cv_path, best_variant


def get_all_cv_paths(cv_dir: Path) -> dict[str, Path]:
    """Get all available CV paths."""
    return {
        name: cv_dir / config["path"]
        for name, config in CV_VARIANTS.items()
    }
