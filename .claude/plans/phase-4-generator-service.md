# Phase 4: Generator Service Implementation

## Status: PENDING

## Overview

Test and validate the Generator service that creates tailored CVs and cover letters using LLM.

## Tasks

### Core Implementation
- [x] Implement `ProfileLoader` class
- [x] Implement profile to context string conversion
- [x] Implement `ResumeGenerator` class
- [x] Implement `CoverLetterGenerator` class
- [x] Implement LLM prompts for generation

### PDF Generation
- [x] Implement `PDFGenerator` class
- [x] Implement markdown to HTML conversion
- [x] Implement WeasyPrint PDF rendering
- [x] Create professional CSS styling

### CLI Interface
- [x] Implement Click-based CLI
- [x] Add `--limit` option
- [x] Add `--force` option (regenerate existing)
- [x] Add `--no-pdf` option
- [x] Add `--daemon` mode

### Testing
- [ ] Configure `config/profile.yaml` with real data
- [ ] Run generator on qualified jobs
- [ ] Review generated resume content
- [ ] Review generated cover letter content
- [ ] Review PDF formatting

### Quality Validation
- [ ] Check resume highlights relevant experience
- [ ] Check cover letter mentions company name
- [ ] Check keywords are incorporated naturally
- [ ] Check PDF renders correctly

## Profile Configuration

Edit `config/profile.yaml`:

```yaml
personal:
  name: "Your Name"
  email: "your.email@example.com"
  phone: "+41 XX XXX XX XX"
  location: "Zurich, Switzerland"
  linkedin: "linkedin.com/in/yourprofile"

summary: |
  Security professional with X years of experience...

experience:
  - company: "Current Company"
    title: "Security Engineer"
    start_date: "2022-01"
    end_date: "Present"
    achievements:
      - "Implemented SIEM solution reducing incident response time by 50%"
      - "Led security assessment for cloud migration project"

skills:
  security:
    - "SIEM (Splunk, Sentinel)"
    - "Penetration Testing"
  programming:
    - "Python"
    - "Bash"
```

## Testing Commands

```bash
# Create output directory
mkdir -p output

# Run generator
python -m generator.main

# Generate for specific number of jobs
python -m generator.main --limit 3

# Regenerate existing
python -m generator.main --force

# Skip PDF (text only)
python -m generator.main --no-pdf

# Check output
ls -la output/
# View PDF
open output/resume_*.pdf
```

## LLM Prompt Tuning

If generated content is not satisfactory:

1. Resume issues:
   - Adjust `src/generator/llm.py` ResumeGenerator prompt
   - Add more specific instructions
   - Adjust temperature (lower = more consistent)

2. Cover letter issues:
   - Adjust CoverLetterGenerator prompt
   - Add company research instructions
   - Adjust tone/formality

## Next Phase

Proceed to Phase 5: End-to-End Testing
