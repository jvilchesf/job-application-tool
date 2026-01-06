"""
RenderCV PDF Generator.
Generates professional PDF CVs using RenderCV from tailored YAML content.
"""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml
from loguru import logger


@dataclass
class PDFGenerationResult:
    """Result of PDF generation."""
    success: bool
    pdf_path: Optional[Path] = None
    yaml_path: Optional[Path] = None
    error: Optional[str] = None


class RenderCVGenerator:
    """Generates professional PDF CVs using RenderCV."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, text: str) -> str:
        """Sanitize text for use in filenames."""
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)

    def _write_yaml(self, cv_data: dict[str, Any], output_path: Path) -> None:
        """Write CV data to YAML file."""
        with open(output_path, "w") as f:
            yaml.dump(cv_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def generate_pdf(
        self,
        cv_data: dict[str, Any],
        job_id: str,
        company: str,
    ) -> PDFGenerationResult:
        """
        Generate PDF from tailored CV data using RenderCV.

        Args:
            cv_data: Tailored CV data in RenderCV YAML format
            job_id: Job ID for filename
            company: Company name for filename

        Returns:
            PDFGenerationResult with paths to generated files
        """
        safe_company = self._sanitize_filename(company)
        base_filename = f"cv_{safe_company}_{job_id[:8]}"

        # Create output directory for this job
        job_output_dir = self.output_dir / base_filename
        job_output_dir.mkdir(parents=True, exist_ok=True)

        # Write tailored YAML
        yaml_path = job_output_dir / f"{base_filename}.yaml"
        self._write_yaml(cv_data, yaml_path)

        try:
            # Run RenderCV
            logger.info(f"Running RenderCV for {company} (job: {job_id[:8]})")

            result = subprocess.run(
                [
                    "rendercv",
                    "render",
                    str(yaml_path),
                    "--output-folder-name",
                    str(job_output_dir),
                ],
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error(f"RenderCV failed: {error_msg}")
                return PDFGenerationResult(
                    success=False,
                    yaml_path=yaml_path,
                    error=f"RenderCV failed: {error_msg}",
                )

            # Find generated PDF (RenderCV puts output in rendercv_output subdirectory)
            pdf_files = list(job_output_dir.glob("**/*.pdf"))
            if not pdf_files:
                return PDFGenerationResult(
                    success=False,
                    yaml_path=yaml_path,
                    error="No PDF file generated",
                )

            # Use the first PDF found (should be the main CV)
            pdf_path = pdf_files[0]

            # Rename to our standard naming convention
            final_pdf_path = job_output_dir / f"{base_filename}.pdf"
            if pdf_path != final_pdf_path:
                pdf_path.rename(final_pdf_path)
                pdf_path = final_pdf_path

            logger.info(f"Generated PDF: {pdf_path}")

            return PDFGenerationResult(
                success=True,
                pdf_path=pdf_path,
                yaml_path=yaml_path,
            )

        except subprocess.TimeoutExpired:
            logger.error("RenderCV timed out after 120 seconds")
            return PDFGenerationResult(
                success=False,
                yaml_path=yaml_path,
                error="RenderCV timed out",
            )
        except FileNotFoundError:
            logger.error("RenderCV not found. Please install: pip install rendercv[full]")
            return PDFGenerationResult(
                success=False,
                yaml_path=yaml_path,
                error="RenderCV not installed",
            )
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return PDFGenerationResult(
                success=False,
                yaml_path=yaml_path,
                error=str(e),
            )

    def generate_cover_letter_pdf(
        self,
        cover_letter: str,
        job_id: str,
        company: str,
        job_title: str,
        candidate_name: str,
    ) -> Optional[Path]:
        """
        Generate PDF for cover letter using simple markdown to PDF.
        Uses WeasyPrint for cover letters (simpler than RenderCV).

        Args:
            cover_letter: Cover letter text
            job_id: Job ID for filename
            company: Company name
            job_title: Job title
            candidate_name: Candidate's name

        Returns:
            Path to generated PDF or None on failure
        """
        try:
            import markdown
            from weasyprint import CSS, HTML

            safe_company = self._sanitize_filename(company)
            base_filename = f"cover_letter_{safe_company}_{job_id[:8]}"

            # Create output directory
            job_output_dir = self.output_dir / f"cv_{safe_company}_{job_id[:8]}"
            job_output_dir.mkdir(parents=True, exist_ok=True)

            # Convert markdown to HTML
            html_content = markdown.markdown(cover_letter)

            # Wrap in document structure
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body>
    <div class="header">
        <h1>{candidate_name}</h1>
        <p class="applying-for">Application for {job_title} at {company}</p>
    </div>
    <div class="content">
        {html_content}
    </div>
</body>
</html>"""

            # CSS styling
            css = CSS(string="""
@page {
    size: A4;
    margin: 2.5cm;
}

body {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
}

.header {
    margin-bottom: 2em;
    border-bottom: 1px solid #ccc;
    padding-bottom: 1em;
}

.header h1 {
    font-size: 18pt;
    margin: 0;
    color: #1a1a1a;
}

.applying-for {
    color: #666;
    font-style: italic;
    margin-top: 0.5em;
}

.content p {
    text-align: justify;
    margin-bottom: 1em;
}

strong {
    font-weight: 600;
}
""")

            # Generate PDF
            pdf_path = job_output_dir / f"{base_filename}.pdf"
            HTML(string=html).write_pdf(pdf_path, stylesheets=[css])

            logger.info(f"Generated cover letter PDF: {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"Cover letter PDF generation failed: {e}")
            return None
