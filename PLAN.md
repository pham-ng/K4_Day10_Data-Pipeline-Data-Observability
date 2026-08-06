# PLAN — Bước 12, 13, 14

Kế hoạch triển khai phase 2 (corruption → re-evaluate → repair → compare) dựa trên `Guide.md` và code hiện có.

## Trạng thái hiện tại

| File | Trạng thái |
| --- | --- |
| `src/ingestion/corruption.py` | stub — `corrupt_clean_dataframe()` raise NotImplementedError |
| `src/pipelines/corruption_flow.py` | stub — `main()` raise NotImplementedError |
| `src/observability/reporting.py` | `generate_corruption_report()` stub; `generate_phase1_report()` đã xong |
| `src/observability/quality.py` | đã xong, dùng lại được |
| `src/evaluation/metrics.py` | đã xong (`evaluate_pipeline`) |
| `src/retrieval/index.py` | đã xong (`LocalEmbeddingIndex.build`) |
| `script/run_corruption_flow.py` | đã có entrypoint |

Baseline artifacts đã tồn tại: `data/clean/papers_clean.*`, `data/eval/test_set.json`, `data/results/baseline_metrics.json`, `data/quality/baseline_quality.json`.

---

## Bước 12 — Corrupt dữ liệu

### 12.1 `src/ingestion/corruption.py`

Signature giữ nguyên:

```python
def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame
```

Nguyên tắc:

- Không mutate `df` gốc → làm việc trên `df.copy()`.
- Deterministic: dùng `random.Random(SEED)` / `numpy.random.default_rng(SEED)` với `SEED = 42` để chạy lại ra cùng kết quả.
- Mỗi thao tác ghi lại vào `log` list: `{"step", "description", "affected_paper_ids", "row_count_before", "row_count_after"}`.

Các corruption scenario (theo Guide):

| # | Scenario | Cách làm | Metric bị ảnh hưởng |
| --- | --- | --- | --- |
| 1 | Drop latest records | df đã sort `published` desc → drop `head(DROP_LATEST_N=3)` | retrieval_hit_rate (mất doc ground truth), freshness (`latest_published` lùi) |
| 2 | Blank summary | 25% row random → `summary = ""`, `summary_chars = 0` | quality check `summary_length`, token_f1 câu hỏi `summary` |
| 3 | Noise vào summary | 20% row → chèn token rác (`"lorem ipsum ###"`, ký tự lặp, HTML tag còn sót) vào giữa summary | chất lượng embedding, judge score |
| 4 | Truncate title | 20% row → `title = title[:15]` | lookup theo exact title fail, retrieval kém |
| 5 | Stale publication date | 30% row → trừ `published` đi 500–900 ngày, tính lại `age_days` tương ứng | quality check `freshness`, câu hỏi `date` sai |
| 6 | Duplicate rows | copy 3 row bất kỳ rồi `pd.concat` (giữ nguyên `paper_id`) | quality check `paper_id_valid` (duplicates > 0) |

Các nhóm row phải chọn **disjoint hoặc có kiểm soát** để log rõ ràng — dùng `rng.choice(index, size, replace=False)` cho từng scenario.

Sau khi corrupt:

7. Rebuild `text_for_embedding` cho toàn bộ df bằng đúng công thức của `cleaning.build_clean_dataframe` (title + summary + `Authors: ...` + `Categories: ...`, qua `normalize_whitespace`). Tách helper `build_text_for_embedding(row)` trong `cleaning.py` và import lại để tránh lặp logic.
8. Cập nhật lại `summary_chars` và `age_days` cho các row bị đổi.
9. Ghi log JSON ra `output_log_path` (= `settings.paths.corruption_log` → `data/results/corruption_log.json`) qua `core.utils.write_json`, payload:

```json
{
  "generated_at": "...",
  "seed": 42,
  "rows_before": 24,
  "rows_after": 24,
  "steps": [ {"step": "drop_latest", "...": "..."} ]
}
```

10. Return df đã reset_index (KHÔNG sort lại — để giữ dấu vết corruption).

### 12.2 Constants đặt đầu file

`SEED`, `DROP_LATEST_N`, `BLANK_SUMMARY_FRACTION`, `NOISE_FRACTION`, `TRUNCATE_TITLE_FRACTION`, `TRUNCATE_TITLE_CHARS`, `STALE_FRACTION`, `STALE_SHIFT_DAYS_RANGE`, `DUPLICATE_ROWS` — không hard-code số trong thân hàm.

---

## Bước 13 — Re-evaluate sau corruption

### 13.1 `src/pipelines/corruption_flow.py` — `main()`

In log theo pattern `[corruption] step i/N: ...` giống `phase1.py`.

```
 1. settings = load_settings()
 2. Guard: nếu thiếu paths.clean_json hoặc baseline_metrics hoặc eval_testset
    -> raise RuntimeError("Chạy run_phase1.py trước.")
 3. baseline_metrics = read_json(paths.baseline_metrics)
    baseline_df     = pd.DataFrame(read_json(paths.clean_json))
 4. CORRUPT
    corrupted_df = corrupt_clean_dataframe(baseline_df, paths.corruption_log)
    write_csv(corrupted_df, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted_df.to_dict("records"))
 5. INDEX + EVAL (corrupted)
    idx_c = LocalEmbeddingIndex.build(corrupted_df, settings,
              embeddings_output_path=paths.corrupted_embeddings_json)   # -> collection "papers-corrupted"
    bundle_c = evaluate_pipeline(settings, idx_c,
              test_set_path=paths.eval_testset,          # DÙNG LẠI test set cũ, không rebuild
              metrics_output_path=paths.corrupted_metrics,
              answers_output_path=paths.corrupted_answers)
 6. OBSERVABILITY (corrupted)
    quality_c   = run_data_quality_checks(corrupted_df, settings, report_name="corrupted")
                  # -> data/quality/corrupted_quality.json
    freshness_c = build_freshness_report(corrupted_df, settings,
                  report_path=paths.quality_dir / "corrupted_freshness.json")
 7. REPAIR — tái tạo từ raw source, không "vá" corrupted df
    records      = load_raw_records(paths.raw_records_json)
                   (nếu settings.refresh_source -> fetch_source_records(settings))
    repaired_df  = build_clean_dataframe(records, run_date=now_utc())
    write_csv / write_json -> paths.repaired_clean_csv / repaired_clean_json
 8. INDEX + EVAL (repaired)
    idx_r = LocalEmbeddingIndex.build(repaired_df, settings,
              embeddings_output_path=paths.repaired_embeddings_json)     # -> "papers-repaired"
    bundle_r = evaluate_pipeline(..., paths.repaired_metrics, paths.repaired_answers)
 9. OBSERVABILITY (repaired)
    quality_r   = run_data_quality_checks(repaired_df, settings, report_name="repaired")
    freshness_r = build_freshness_report(repaired_df, settings,
                  report_path=paths.quality_dir / "repaired_freshness.json")
10. REPORT
    generate_corruption_report(paths.comparison_report, ...)
11. In bảng tóm tắt 3 cột ra stdout.
```

Lưu ý kỹ thuật:

- `build_clean_dataframe` cần `PaperRecord`; `load_raw_records` trả đúng type đó → import từ `ingestion.crossref`.
- Ba collection tách biệt (`papers-baseline` / `papers-corrupted` / `papers-repaired`) đã được `_derive_collection_name` map sẵn theo embeddings path → không đụng vào index baseline.
- `evaluate_pipeline` gọi LLM judge cho từng câu hỏi × 2 lần (corrupted + repaired) → chạy lâu; có fallback heuristic judge nếu LLM lỗi nên không block.
- Repaired ≠ baseline byte-by-byte nếu `age_days` đổi theo ngày chạy — chấp nhận, ghi chú trong report.

### 13.2 Artifacts kỳ vọng sau khi chạy

```
data/clean/papers_clean_corrupted.{csv,json}
data/clean/papers_clean_repaired.{csv,json}
data/embeddings/papers_embeddings_{corrupted,repaired}.json
data/results/corruption_log.json
data/results/{corrupted,repaired}_metrics.json
data/results/{corrupted,repaired}_answers.json
data/quality/{corrupted,repaired}_quality.json
data/quality/{corrupted,repaired}_freshness.json
data/reports/corruption_report.md
```

---

## Bước 14 — So sánh baseline / corrupted / repaired

### 14.1 `generate_corruption_report()` trong `src/observability/reporting.py`

Giữ nguyên signature đã khai báo (8 tham số). Cấu trúc markdown:

1. **Header** — tiêu đề + `generated_at`.
2. **Corruption scenarios** — bảng đọc từ `corruption_log.json` (thêm tham số `corruption_log: dict | None = None` với default để không phá signature cũ).
3. **Metrics comparison** — bảng chính:

| Metric | Baseline | Corrupted | Repaired | Δ (corrupt−base) | Δ (repair−base) |
| --- | --- | --- | --- | --- | --- |
| retrieval_hit_rate | | | | | |
| mean_token_f1 | | | | | |
| judge_accuracy | | | | | |
| mean_judge_score | | | | | |

Helper `_delta(new, base)` → chuỗi `+0.0000` / `-0.1250`, trả `n/a` nếu thiếu giá trị.

4. **Data quality comparison** — bảng `Check | Baseline | Corrupted | Repaired` với PASS/FAIL từng check (`row_count`, `paper_id_valid`, `title_not_null`, `summary_length`, `freshness`) + dòng Overall. Dùng `_checks_table` sẵn có làm tham chiếu, viết thêm `_checks_matrix(...)` gộp 3 report theo `name`.
5. **Freshness comparison** — `latest_published`, `oldest_published`, `stale_rows / total_rows`, `is_fresh` cho 3 dataset.
6. **Kết luận** — sinh tự động, không viết cứng:
   - `degraded = corrupted.retrieval_hit_rate < baseline.retrieval_hit_rate` → câu khẳng định "dữ liệu xấu làm giảm performance", kèm % giảm.
   - `recovered = repaired.retrieval_hit_rate >= baseline.retrieval_hit_rate * 0.95` → "repair phục hồi performance".
   - Nếu không đúng kỳ vọng → in cảnh báo để người đọc biết cần tăng cường độ corruption.
7. Ghi file bằng `write_text(report_path, ...)`.

### 14.2 Bonus (theo Rubric mục Bonus)

- Thêm `script/run_comparison.py` (hoặc flag `--report-only`) đọc lại các file metrics đã có và render lại report mà không chạy eval — tiện sửa report.
- Vẽ bar chart matplotlib 4 metric × 3 dataset → `data/reports/metrics_comparison.png`, nhúng vào markdown.

---

## Thứ tự thực thi

1. Tách `build_text_for_embedding()` ra khỏi `cleaning.py`.
2. Viết `corruption.py` (bước 12).
3. Viết `generate_corruption_report()` (bước 14) — làm trước pipeline để pipeline chỉ việc gọi.
4. Viết `corruption_flow.main()` (bước 13).
5. `uv run python script/run_corruption_flow.py`.
6. Verify: đối chiếu bảng trong `corruption_report.md` với các file JSON thực tế (rubric trừ điểm nếu report không match artifact).
7. Chạy lại `run_phase1.py` một lần cuối để chắc baseline collection không bị ảnh hưởng.

## Rủi ro cần canh

| Rủi ro | Xử lý |
| --- | --- |
| Corruption quá nhẹ → metrics không giảm rõ | Tăng `DROP_LATEST_N` và các fraction; drop record thuộc ground_truth của test set |
| `text_for_embedding` rỗng sau khi blank summary + truncate title | Vẫn giữ row (đó là mục đích), nhưng đảm bảo không NaN → dùng `""` |
| Chroma collection cũ còn sót | `LocalEmbeddingIndex.build` đã `delete_collection` trước khi tạo |
| Chi phí LLM judge | Có thể set `LLM_PROVIDER` rẻ hoặc chấp nhận fallback heuristic; `RUN_RAGAS` để mặc định off |
| Test set trỏ tới paper đã bị drop | Đúng như thiết kế — đó là nguồn giảm `retrieval_hit_rate` |
