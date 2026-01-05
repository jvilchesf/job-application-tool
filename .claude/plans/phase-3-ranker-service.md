# Phase 3: Ranker Service Implementation

## Status: PENDING

## Overview

Test and validate the Ranker service that scores jobs using template-based keyword matching and LLM translation.

## Tasks

### Core Implementation
- [x] Implement `TemplateMatcher` class
- [x] Implement keyword matching with word boundaries
- [x] Implement title bonus scoring
- [x] Implement negative keyword handling
- [x] Load templates from YAML

### Translation
- [x] Implement `JobTranslator` class
- [x] Implement language detection (German indicators)
- [x] Implement OpenAI translation
- [x] Store translated description in database

### CLI Interface
- [x] Implement Click-based CLI
- [x] Add `--no-translate` option
- [x] Add `--limit` option
- [x] Add `--reprocess` option
- [x] Add `--daemon` mode

### Testing
- [ ] Run ranker on scraped jobs
- [ ] Verify scoring logic matches expectations
- [ ] Test translation with German job descriptions
- [ ] Verify status updates (qualified/disqualified)

### Validation
- [ ] Review qualified jobs manually
- [ ] Adjust template keywords if needed
- [ ] Fine-tune score thresholds

## Scoring Algorithm Details

```python
# For each job:
trigger_score = len(matched_triggers) * 10
title_bonus = len(title_trigger_matches) * 5  # Extra for title matches
support_score = len(matched_support) * 4
negative_score = len(matched_negative) * -15

total = trigger_score + title_bonus + support_score + negative_score
total = max(0, total)  # Don't go negative

passed = len(matched_triggers) >= 2 AND total >= 30
```

## Testing Commands

```bash
# Run ranker on pending jobs
python -m ranker.main

# Skip translation
python -m ranker.main --no-translate

# Reprocess all jobs
python -m ranker.main --reprocess

# Check results
docker exec -it mongodb mongosh job_application --eval "db.jobs.aggregate([{\$group: {_id: '\$status', count: {\$sum: 1}}}])"
docker exec -it mongodb mongosh job_application --eval "db.jobs.find({status: 'qualified'}).sort({score: -1}).limit(5).pretty()"
```

## Template Tuning

After initial run, review results:

1. Check false positives (qualified but irrelevant)
   - Add negative keywords
   - Increase min_score threshold

2. Check false negatives (disqualified but relevant)
   - Add trigger/support keywords
   - Decrease min_score threshold

## Next Phase

Proceed to Phase 4: Generator Service Testing
