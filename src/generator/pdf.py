"""
PDF generation for resumes and cover letters.
Uses WeasyPrint for HTML-to-PDF conversion with custom styling.
"""

import tempfile
from pathlib import Path
from typing import Optional

import markdown
from loguru import logger
from weasyprint import HTML, CSS


# Modern, clean CSS for PDF generation
PDF_CSS = """
@page {
    size: A4;
    margin: 2cm 2.5cm;
}

body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #333;
}

h1 {
    font-size: 24pt;
    font-weight: 600;
    margin-bottom: 0.3em;
    color: #1a1a1a;
    border-bottom: 2px solid #2563eb;
    padding-bottom: 0.2em;
}

h2 {
    font-size: 14pt;
    font-weight: 600;
    color: #2563eb;
    margin-top: 1.2em;
    margin-bottom: 0.5em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

h3 {
    font-size: 12pt;
    font-weight: 600;
    margin-top: 0.8em;
    margin-bottom: 0.3em;
    color: #1a1a1a;
}

p {
    margin-bottom: 0.5em;
}

ul {
    margin-left: 1.5em;
    margin-bottom: 0.5em;
}

li {
    margin-bottom: 0.3em;
}

strong {
    font-weight: 600;
}

/* Contact info styling */
p:first-of-type {
    color: #666;
    font-size: 10pt;
}

/* Links */
a {
    color: #2563eb;
    text-decoration: none;
}

/* Cover letter specific */
.cover-letter {
    max-width: 700px;
}

.cover-letter p {
    text-align: justify;
    margin-bottom: 1em;
}

.signature {
    margin-top: 2em;
}
"""


class PDFGenerator:
    """Generates PDF documents from Markdown content."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("./output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _markdown_to_html(self, content: str, is_cover_letter: bool = False) -> str:
        """Convert Markdown to HTML."""
        # Convert Markdown to HTML
        html_content = markdown.markdown(
            content,
            extensions=["tables", "fenced_code"],
        )

        # Wrap in document structure
        wrapper_class = "cover-letter" if is_cover_letter else "resume"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body class="{wrapper_class}">
{html_content}
</body>
</html>"""

        return html

    def generate_pdf(
        self,
        content: str,
        filename: str,
        is_cover_letter: bool = False,
    ) -> Path:
        """
        Generate PDF from Markdown content.

        Args:
            content: Markdown content
            filename: Output filename (without extension)
            is_cover_letter: Whether this is a cover letter (affects styling)

        Returns:
            Path to generated PDF
        """
        html_content = self._markdown_to_html(content, is_cover_letter)
        output_path = self.output_dir / f"{filename}.pdf"

        # Generate PDF
        html = HTML(string=html_content)
        css = CSS(string=PDF_CSS)

        html.write_pdf(output_path, stylesheets=[css])

        logger.info(f"Generated PDF: {output_path}")
        return output_path

    def generate_resume_pdf(
        self,
        content: str,
        job_id: str,
        company: str,
    ) -> Path:
        """Generate resume PDF with standardized filename."""
        # Sanitize company name for filename
        safe_company = "".join(c if c.isalnum() else "_" for c in company)
        filename = f"resume_{safe_company}_{job_id}"
        return self.generate_pdf(content, filename, is_cover_letter=False)

    def generate_cover_letter_pdf(
        self,
        content: str,
        job_id: str,
        company: str,
    ) -> Path:
        """Generate cover letter PDF with standardized filename."""
        safe_company = "".join(c if c.isalnum() else "_" for c in company)
        filename = f"cover_letter_{safe_company}_{job_id}"
        return self.generate_pdf(content, filename, is_cover_letter=True)
