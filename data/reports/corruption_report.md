# Corruption Impact Report

Generated at: 2026-08-06T09:02:21.141146+00:00

So sanh 3 dataset: **baseline** (clean) / **corrupted** (co loi) / **repaired** (build lai tu raw source). Ca ba dung chung mot evaluation test set.

## 1. Corruption scenarios

| Step | Description | Affected rows | Rows before | Rows after |
| --- | --- | --- | --- | --- |
| `drop_latest` | Xoa 3 record moi nhat theo published desc. | 3 | 24 | 21 |
| `blank_summary` | Xoa trang summary cua 5 row (~25%). | 5 | 21 | 21 |
| `noise_summary` | Chen token rac vao summary cua 4 row (~20%). | 4 | 21 | 21 |
| `truncate_title` | Cat title con 15 ky tu cho 4 row. | 4 | 21 | 21 |
| `stale_published` | Lui published 500-900 ngay cho 6 row (~30%). | 6 | 21 | 21 |
| `duplicate_rows` | Nhan doi 3 row (giu nguyen paper_id -> duplicate id). | 3 | 21 | 24 |
| `rebuild_derived_fields` | Tinh lai summary_chars, age_days va text_for_embedding tren toan bo dataframe. | 0 | 24 | 24 |

## 2. Evaluation metrics

| Metric | Baseline | Corrupted | Repaired | Delta (corrupt-base) | Delta (repair-base) |
| --- | --- | --- | --- | --- | --- |
| Retrieval hit rate | 1.0000 | 0.8500 | 1.0000 | -0.1500 | +0.0000 |
| Mean token F1 | 0.9554 | 0.6127 | 0.9554 | -0.3427 | +0.0000 |
| Judge accuracy | 0.9667 | 0.7167 | 0.9667 | -0.2500 | +0.0000 |
| Mean judge score | 4.8667 | 3.8667 | 4.8667 | -1.0000 | +0.0000 |

Samples: baseline=60, corrupted=60, repaired=60

## 3. Data quality

| Check | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| row_count | PASS | PASS | PASS |
| paper_id_valid | PASS | FAIL | PASS |
| title_not_null | PASS | PASS | PASS |
| summary_length | PASS | PASS | PASS |
| freshness | PASS | PASS | PASS |
| **Overall** | **PASS** | **FAIL** | **PASS** |

## 4. Freshness

| Field | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| latest_published | 2028-06-15 | 2028-06-15 | 2028-06-15 |
| oldest_published | 2026-12-31 | 2024-08-26 | 2026-12-31 |
| stale_rows / total_rows | 0 / 24 | 6 / 24 | 0 / 24 |
| is_fresh | YES | NO | YES |

## 5. Ket luan

- **Du lieu xau lam giam performance**: retrieval hit rate giam tu 1.0000 xuong 0.8500 (-15.0%).
- **Repair phuc hoi performance**: retrieval hit rate quay lai 1.0000 (>= 95% baseline 1.0000).
- Mean token F1: 0.9554 -> 0.6127 (corrupted) -> 0.9554 (repaired).
- Judge accuracy: 0.9667 -> 0.7167 (corrupted) -> 0.9667 (repaired).
- Mean judge score: 4.8667 -> 3.8667 (corrupted) -> 4.8667 (repaired).
- Data quality overall: corrupted **FAIL**, repaired **PASS**.
- Luu y: `age_days` duoc tinh theo ngay chay nen repaired co the khong trung baseline byte-by-byte, day la hanh vi mong doi.

## 6. Bieu do

![Metrics comparison](metrics_comparison.png)
