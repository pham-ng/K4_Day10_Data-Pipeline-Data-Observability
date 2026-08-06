# Phase 1 Baseline Report

Generated at: 2026-08-06T08:57:12.150320+00:00

## Source

- **API**: Crossref REST API
- **Query**: agentic retrieval augmented generation large language model
- **Filter**: from-pub-date:2026-02-07,has-abstract:true
- **Raw records**: 24
- **Clean records**: 24

## Evaluation Metrics

- **Samples**: 60
- **Retrieval hit rate**: 1.0000
- **Mean token F1**: 0.9554
- **Judge accuracy**: 0.9667
- **Mean judge score**: 4.8667
- **Ragas**:
- **skipped**: Set RUN_RAGAS=1 to enable the slower Ragas pass.

## Data Quality

Overall: **PASS** (24 rows)

| Check | Status | Details |
| --- | --- | --- |
| row_count | PASS | `{'row_count': 24}` |
| paper_id_valid | PASS | `{'null_or_empty': 0, 'duplicates': 0}` |
| title_not_null | PASS | `{'null_or_empty': 0}` |
| summary_length | PASS | `{'min_chars_threshold': 20, 'short_rows': 2, 'short_fraction': 0.0833}` |
| freshness | PASS | `{'freshness_threshold_days': 180, 'stale_rows': 0, 'stale_fraction': 0.0, 'missing_age_days': 0}` |

## Freshness

- **Latest published**: 2028-06-15
- **Oldest published**: 2026-12-31
- **Stale rows**: 0 / 24
- **Freshness threshold (days)**: 180
- **Is fresh**: YES
