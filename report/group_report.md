# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4                         |
| Tên nhóm         | K4-DAY10-2A202602040-PhamNguyenKhanhMinh |
| Repository         | https://github.com/pham-ng/K4_Day10_Data-Pipeline-Data-Observability.git |
| Ngày hoàn thành | 2026-08-06                 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Phạm Nguyễn Khánh Minh | 2A202602040 | Lead Engineer & Architect (Làm cá nhân toàn bộ) | Toàn bộ dự án (`src/ingestion`, `src/retrieval`, `src/evaluation`, `src/observability`, `src/pipelines`) |

## 2. Tóm tắt kết quả

Dự án đã xây dựng hoàn chỉnh một Data Pipeline end-to-end kết hợp với Data Observability & Quality Monitoring cho ứng dụng RAG Agent.
Baseline Pipeline thu thập thành công 24 bản ghi nghiên cứu từ Crossref API, làm sạch dữ liệu và đánh giá trên bộ test 60 câu hỏi đã đóng băng, đạt `retrieval_hit_rate` = **1.0000**, `mean_token_f1` = **0.9554**, `judge_accuracy` = **0.9667** và `mean_judge_score` = **4.8667/5.0** (OpenAI `gpt-4o-mini`).

Kịch bản Compound Data Corruption gây lỗi 6 bài mới nhất, chèn nhiễu HTML rác/xóa trắng tóm tắt 35%, cắt tiêu đề và làm cũ dữ liệu đã làm sụt giảm nghiêm trọng hiệu năng của Agent: `retrieval_hit_rate` rớt xuống **0.6833** (giảm 31.7%), `mean_token_f1` rớt xuống **0.4891** (giảm 46.6%), và các bài kiểm tra Data Quality báo **`FAIL`** (phát hiện 4 dòng trùng lặp và 8 dòng cũ). Quy trình Data Repair phục hồi lại dữ liệu chuẩn từ Raw Snapshot thô (`data/raw/crossref_records.json`), thành công đưa toàn bộ chỉ số RAG và Quality Check quay lại mốc tuyệt đối 100% so với Baseline.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records (data/raw/crossref_records.json)
    -> cleaning và data modeling (data/clean/papers_clean.csv)
    -> embedding + ChromaDB index (data/embeddings/chroma_db)
    -> evaluation baseline (data/results/baseline_metrics.json & baseline_answers.json)
    -> quality/freshness reports (data/quality/baseline_quality.json)
    -> compound corruption (data/clean/papers_corrupted.csv & corruption_log.json)
    -> re-index và re-evaluate (corrupted_metrics.json & corrupted_quality.json)
    -> repair từ dữ liệu nguồn thô (papers_clean_repaired.csv)
    -> comparison report & chart (data/reports/corruption_report.md & metrics_comparison.png)
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref REST API | Crawl JSON thô, xử lý retry/backoff, lưu raw snapshot | `data/raw/crossref_records.json` | Phạm Nguyễn Khánh Minh |
| Cleaning          | Raw JSON records | Trích xuất DOI, tác giả, tóm tắt, chuẩn hóa ngày ISO, sinh `text_for_embedding` | `data/clean/papers_clean.csv` | Phạm Nguyễn Khánh Minh |
| Embedding/index   | Cleaned DataFrame | Tạo vector nhúng `MiniLM` và lưu trữ tập trung ChromaDB collection | `data/embeddings/` | Phạm Nguyễn Khánh Minh |
| Evaluation        | Cleaned index + Frozen test set | Tìm kiếm Top-K, gọi RAG Agent, tính Token F1, LLM Judge | `data/results/baseline_metrics.json` | Phạm Nguyễn Khánh Minh |
| Observability     | Cleaned/Corrupted DataFrame | Kiểm tra Completeness, Uniqueness, Freshness | `data/quality/baseline_quality.json` | Phạm Nguyễn Khánh Minh |
| Corruption/repair | Cleaned DataFrame / Raw Snapshot | Gây lỗi đa tầng và phục hồi lại từ Raw Snapshot | `data/clean/papers_corrupted.csv` | Phạm Nguyễn Khánh Minh |
| Orchestration     | CLI Entrypoints | Điều phối Phase 1 Baseline và Phase 2 Corruption Flow | `data/reports/corruption_report.md` | Phạm Nguyễn Khánh Minh |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `openai` |
| `LLM_MODEL`                | `gpt-4o-mini` |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | `24` |
| Retrieval `top_k`           | `3` |
| Freshness threshold          | `180` ngày |
| Random seed                | `42` |

### Lệnh cài đặt

```bash
uv sync
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công | 2026-08-06 19:24 | `data/results/baseline_metrics.json` |
| Corruption flow   | Thành công | 2026-08-06 20:08 | `data/reports/corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API (`https://api.crossref.org/works`) |
| Query/filter                | `query=robotics+OR+artificial+intelligence` |
| Thời điểm lấy dữ liệu | 2026-08-06 |
| Số record nhận được    | 24 |
| Cơ chế retry/backoff      | Exponential Backoff 3 lần retry |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | `str` | Có | Mã định danh duy nhất (DOI) | Lấy DOI làm ID |
| `title` | `str` | Có | Tiêu đề bài báo | Bỏ khoảng trắng dư |
| `summary` | `str` | Có | Tóm tắt nội dung bài báo | Loại bỏ thẻ HTML/XML rác |
| `authors_joined` | `str` | Không | Danh sách tác giả ghép chuỗi | Điền `Unknown Author` nếu rỗng |
| `published` | `str` | Có | Ngày xuất bản định dạng YYYY-MM-DD | Chuẩn hóa ISO 8601 |
| `text_for_embedding` | `str` | Có | Văn bản gộp phục vụ tạo Vector Index | Gộp Title + Summary + Authors |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Loại bỏ HTML/XML tags khỏi summary | Validity / Format | 24 | RegEx cleaning |
| Chuẩn hóa ngày ISO 8601 YYYY-MM-DD | Timeliness / Validity | 24 | `datetime.strptime` |
| Loại bỏ bản ghi thiếu `paper_id` hoặc `title` | Completeness | 0 | Filter `dropna` |

**Tạo `text_for_embedding`, document ID và `age_days`:**
- `text_for_embedding` = `f"{title} {summary} Authors: {authors_joined}"`.
- `document ID` = DOI duy nhất (`paper_id`).
- `age_days` = khoảng cách tính theo ngày từ `published` đến thời điểm chạy.

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 60 câu hỏi |
| Các `question_type`                    | `summary` (20), `authors` (20), `date` (20) |
| Ground-truth document ID                 | Gắn trực tiếp `paper_id` tương ứng từ CSDL |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection                  | ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`) |
| Retrieval `top_k`                       | 3 |
| LLM provider/model                       | OpenAI `gpt-4o-mini` |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (Frozen tại Checkpoint C2) |

**Giải thích việc đóng băng Test set:**
Bộ câu hỏi test được đóng băng tuyệt đối nhằm duy trì hệ quy chiếu cố định. Nếu mỗi pha tạo mới bộ đề, sự biến động điểm số sẽ bị nhiễu do độ khó câu hỏi khác nhau thay vì phản ánh tác động của chất lượng dữ liệu.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/crossref_records.json` | Có | 24 bản ghi JSON |
| Cleaned dataset          | `data/clean/papers_clean.csv` | Có | 24 dòng dữ liệu sạch |
| Embedding manifest/index | `data/embeddings/chroma_db` | Có | Vector store ChromaDB |
| Evaluation set           | `data/eval/test_set.json` | Có | 60 câu hỏi frozen |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Hit rate=1.0, F1=0.9554 |
| Quality/freshness        | `data/quality/baseline_quality.json` | Có | PASS 100% |
| Baseline report          | `data/reports/phase1_report.md` | Có | Báo cáo Pha 1 Markdown |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` | **`1.0000`** | Tìm kiếm vector ChromaDB khớp đúng 100% tài liệu |
| `mean_token_f1`      | **`0.9554`** | Khớp từ vựng rất cao giữa câu trả lời và ground truth |
| `judge_accuracy`     | **`0.9667`** | OpenAI `gpt-4o-mini` đánh giá 58/60 câu trả lời chính xác |
| `mean_judge_score`   | **`4.8667`** | Điểm trung bình 4.87 / 5.0 |
| Ragas                | Skipped | Tránh lỗi xung đột embedding type và đảm bảo tốc độ |

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `row_count` | Completeness | >= 1 | PASS (`24` dòng) | `baseline_quality.json` |
| `paper_id_valid` | Uniqueness | Không null, 0 trùng lặp | PASS (`0` lỗi) | `baseline_quality.json` |
| `title_not_null` | Completeness | Không null/rỗng | PASS (`0` lỗi) | `baseline_quality.json` |
| `summary_length` | Completeness | Độ dài >= 20 ký tự | PASS (phù hợp) | `baseline_quality.json` |
| `freshness` | Timeliness | Tuổi dữ liệu <= 180 ngày | PASS (`0` quá hạn) | `baseline_quality.json` |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Cleaned Dataset (`papers_clean.csv`) |
| Timestamp mới nhất       | `2028-06-15` |
| Ngưỡng freshness         | `180` ngày |
| Trạng thái baseline      | `Fresh` |
| Lý do                     | Tất cả bài báo đều cập nhật trong mốc cho phép |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| `drop_latest` | Xóa 6 bài mới nhất | 6 | `freshness: FAIL` | `hit_rate` giảm từ 1.0 xuống 0.6833 | Load lại Raw JSON snapshot |
| `blank_summary` | Xóa trắng summary | 6 | `summary_length: FAIL` | `token_f1` giảm rớt xuống 0.4891 | Re-extract từ Raw JSON |
| `noise_summary` | Chèn HTML rác & noise | 6 | Quality warning | Cổng embedding tính sai vector | Re-clean text |
| `truncate_title` | Cắt tiêu đề còn 10 char | 7 | Title validity warning | Sai lệch tra cứu exact title | Phục hồi title chuẩn từ Raw |
| `stale_published` | Lùi ngày 500-900 ngày | 7 | `freshness: FAIL` | 8 dòng báo quá hạn | Reset ngày xuất bản thô |
| `duplicate_rows` | Nhân đôi 4 dòng | 4 | `paper_id_valid: FAIL` | 4 lỗi trùng lặp | Deduplicate bằng DOI |

**Corruption log:**
- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi nhận đầy đủ 6 bước phá hoại, liệt kê chính xác các `paper_id` bị tác động.

**Giải thích cách repair:**
Repair lấy dữ liệu từ `data/raw/crossref_records.json` thô ban đầu để chạy lại pipeline làm sạch. Điều này đảm bảo tính nhất quán (Immutable Snapshot) và khả năng tái lập (Reproducibility) mà không phụ thuộc vào đường truyền mạng live API.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   | **`1.0000`** | **`0.6833`** | **`1.0000`** | **`-0.3167`** | **`100%`** | Xóa bài báo & cắt tiêu đề làm sụt giảm 31.7% khả năng truy hồi |
| `mean_token_f1`        | **`0.9554`** | **`0.4891`** | **`0.9554`** | **`-0.4664`** | **`100%`** | Summary bị chèn rác làm rớt F1 hơn 46.6% xuống < 0.50 |
| `judge_accuracy`       | **`0.9667`** | **`0.5167`** | **`0.9667`** | **`-0.4500`** | **`100%`** | OpenAI LLM Judge rớt 45% do câu trả lời thiếu ngữ cảnh |
| `mean_judge_score`     | **`4.8667`** | **`3.1000`** | **`4.8667`** | **`-1.7667`** | **`100%`** | Điểm chất lượng AI rớt gần 1.8 điểm |
| Quality checks pass/fail | `PASS` | `FAIL` | `PASS` | Phát hiện lỗi trùng & quá hạn | `100%` | Trở lại PASS toàn bộ |
| Freshness status         | `Fresh` | `Stale` | `Fresh` | 8 dòng bị thâm hụt ngày | `100%` | Phục hồi lại dữ liệu tươi mới |

**Hai kết luận có quan hệ nhân quả:**
1. **Compound Corruption ➔ Sụt giảm chỉ số RAG Agent**: Khi làm rỗng/chèn nhiễu 35% tóm tắt và xóa 6 bài báo mới nhất, chất lượng vector nhúng ChromaDB bị biến dạng đại số ➔ Kéo theo `retrieval_hit_rate` giảm 31.7% và `mean_token_f1` giảm rớt xuống 0.4891.
2. **Data Repair ➔ Phục hồi 100% hiệu năng**: Khi chạy lại luồng Cleaning từ Raw Snapshot `crossref_records.json`, dữ liệu sạch được tái tạo ➔ ChromaDB Vector Index được làm mới ➔ Đưa toàn bộ chỉ số RAG Agent và Data Quality Check trở lại mốc 100% tuyệt đối.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi chạy Ragas trên môi trường local với `MiniLMEmbeddings`, thư viện Ragas bị crash do lỗi xung đột lớp Embedding wrapper.
- **Nguyên nhân:** Thư viện Ragas v0.1/v0.2 yêu cầu mô hình Embedding có chuẩn giao tiếp cụ thể với OpenAI/HuggingFace API.
- **Cách xử lý:** Cập nhật `metrics.py` tự động chuyển sang `OpenAIEmbeddings` tương thích khi sử dụng OpenAI Provider, hoặc cho phép bật/tắt an toàn qua cờ `RUN_RAGAS`.
- **Cách xác minh:** Kiểm tra `baseline_metrics.json` hiển thị mượt mà không làm dừng tiến trình Pipeline.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Số lượng bài báo Crossref còn nhỏ (24 bài) | Độ bao phủ dữ liệu vừa phải | Mở rộng API query thu thập 500-1000 bài báo |
| LLM Judge tốn API Quota | Cần quản lý OpenAI Credits | Tích hợp vLLM / Ollama Local Judge tự host |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
