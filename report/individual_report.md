# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Phạm Nguyễn Khánh Minh     |
| MSSV               | 2A202602040                |
| Khóa/Lớp         | K4                         |
| Tên nhóm         | K4-DAY10-2A202602040-PhamNguyenKhanhMinh |
| Vai trò chính    | Lead Engineer & Architect (Thực hiện cá nhân 100%) |
| Repository         | https://github.com/pham-ng/K4_Day10_Data-Pipeline-Data-Observability.git |
| Ngày hoàn thành | 2026-08-06                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Ingestion & Crawling | `src/ingestion/crossref.py` | Crossref REST API | `data/raw/crossref_records.json` | Hoàn thành |
| Data Cleaning | `src/ingestion/cleaning.py` | Raw JSON records | `data/clean/papers_clean.csv` | Hoàn thành |
| Vector Indexing | `src/retrieval/index.py`, `embeddings.py` | Cleaned DataFrame | `data/embeddings/chroma_db` | Hoàn thành |
| RAG QA Agent & LLM | `src/retrieval/qa.py`, `llm.py` | User Question + Context | RAG Answer | Hoàn thành |
| Test Generator & Eval | `src/evaluation/test_generator.py`, `metrics.py` | Cleaned DataFrame | `data/eval/test_set.json`, `baseline_metrics.json` | Hoàn thành |
| Observability & Quality | `src/observability/quality.py`, `reporting.py` | Cleaned/Corrupted DF | `data/quality/*.json`, `phase1_report.md` | Hoàn thành |
| Corruption & Repair | `src/ingestion/corruption.py`, `pipelines/corruption_flow.py` | Cleaned DF & Raw JSON | `papers_corrupted.csv`, `corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Tích hợp & Đóng gói CLI | Toàn bộ dự án | `script/run_phase1.py` và `script/run_corruption_flow.py` chạy thông suốt và mượt mà 100% |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Crawl dữ liệu Crossref | `src/ingestion/crossref.py` | `data/raw/crossref_records.json` | `uv run python script/run_phase1.py` |
| Xây dựng ChromaDB Vector Store | `src/retrieval/index.py` | Collection `papers-baseline` | `ChromaDB PersistentClient` query ok |
| Đánh giá 60 câu hỏi frozen | `src/evaluation/metrics.py` | `baseline_metrics.json` | Hit rate = 1.0, Token F1 = 0.9554 |
| Gây lỗi & Phục hồi dữ liệu | `src/pipelines/corruption_flow.py` | `corruption_report.md` | Hit rate rớt 0.6833 ➔ phục hồi 1.0000 |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Xây dựng Data Pipeline tự động kết hợp Data Observability cho RAG Agent, đo lường tác động của lỗi dữ liệu (Data Corruption) lên độ chính xác của AI và khả năng phục hồi dữ liệu từ nguồn snapshot thô (Data Repair).

### Cách triển khai
- Trích xuất dữ liệu bài báo khoa học từ Crossref API, làm sạch HTML/XML rác và chuẩn hóa ngày xuất bản sang ISO 8601.
- Nhúng văn bản bằng `sentence-transformers/all-MiniLM-L6-v2` và lưu trữ trong ChromaDB Vector Store.
- Sinh bộ 60 câu hỏi kiểm thử (`test_set.json`) và đóng băng tuyệt đối để làm hệ quy chiếu (Checkpoint C2).
- Sử dụng OpenAI `gpt-4o-mini` làm RAG Answer Generator và LLM Judge.
- Xây dựng 6 kịch bản gây lỗi tổng hợp (**Compound Corruption**) tác động 35-40% số dòng dữ liệu.
- Phục hồi lại dữ liệu chuẩn từ Raw Snapshot `crossref_records.json` và đo lường sự hồi phục của chỉ số.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Crossref REST API response thô |
| Output                         | `baseline_metrics.json`, `corruption_report.md`, `metrics_comparison.png` |
| Module phụ thuộc             | `pandas`, `chromadb`, `sentence-transformers`, `openai`, `pydantic` |
| Module sử dụng output        | `script/run_phase1.py`, `script/run_corruption_flow.py` |
| Điều kiện lỗi cần xử lý | Xử lý Rate Limit 429 với Exponential Backoff |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Baseline hit rate 1.0, Corrupted hit rate giảm mạnh < 0.70, Repaired hit rate hồi phục 1.0.
- **Kết quả thực tế:** Baseline 1.0000 -> Corrupted 0.6833 -> Repaired 1.0000.
- **Artifact/log:** `data/reports/corruption_report.md` và `data/reports/metrics_comparison.png`.

## 5. Một quyết định kỹ thuật quan trọng

### Quyết định 1: Áp dụng kịch bản Gây lỗi Đa tầng / Tổng hợp (Compound Corruption) thay vì Gây lỗi đơn lẻ
- **Bối cảnh:** Lựa chọn phương pháp phá hoại dữ liệu để đo lường mức độ ảnh hưởng đến RAG Agent.
- **Các phương án đã cân nhắc:** 
  1. *Gây lỗi đơn lẻ (Single Field Injection)*: Chỉ xóa tóm tắt hoặc chỉ xóa bài báo trên các dòng riêng biệt.
  2. *Gây lỗi đa tầng tổng hợp (Compound Corruption)*: Phối hợp đồng thời nhiều kịch bản lỗi trên cùng các dòng dữ liệu (vừa xóa 6 bài báo mới nhất, vừa làm rỗng/chèn nhiễu HTML 35% tóm tắt, vừa cắt tiêu đề 10 ký tự và lùi ngày xuất bản).
- **Phương án đã chọn:** Phương án 2 (Compound Corruption).
- **Lý do:** Mô phỏng chính xác các sự cố phức hợp trong thực tế vận hành Data Pipeline khi nhiều khâu bị lỗi cùng lúc.
- **Bằng chứng quyết định phù hợp:** Chỉ số RAG sụt giảm rõ rệt và sâu hơn nhiều so với lỗi đơn lẻ: `retrieval_hit_rate` giảm 31.7% (từ 1.0000 rớt xuống **0.6833**) và `mean_token_f1` giảm rớt nặng nề 46.6% (từ 0.9554 rớt thẳng xuống **0.4891** - rớt sâu dưới mốc 0.50), làm nổi bật vai trò của Data Observability & Data Repair.

### Quyết định 2: Tái dựng dữ liệu khôi phục (Data Repair) từ Raw JSON Snapshot cục bộ
- **Bối cảnh:** Lựa chọn nguồn dữ liệu để phục hồi ở bước Data Repair.
- **Các phương án đã cân nhắc:** 
  1. Gọi lại Crossref Live REST API khi chạy bước Repair.
  2. Nạp dữ liệu từ tệp Snapshot thô `data/raw/crossref_records.json` đã lưu tại Checkpoint C1.
- **Phương án đã chọn:** Phương án 2 (Tái dựng từ Raw JSON Snapshot cục bộ).
- **Lý do:** Đảm bảo tính nhất quán (Immutable Snapshot), khả năng tái lập thử nghiệm (Reproducibility) và giúp pipeline chạy tức thì mà không lo bị lỗi mạng hay vướng API Rate Limit.
- **Bằng chứng quyết định phù hợp:** Quá trình Repair đưa 100% các chỉ số RAG (`hit_rate` = 1.0000, `token_f1` = 0.9554) và Data Quality Check trở lại mốc Baseline tuyệt đối.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi chạy OpenAI LLM Judge trên 60 câu hỏi kiểm thử liên tục, hệ thống gặp lỗi Rate Limit HTTP 429 từ OpenAI API.
- **Lệnh hoặc bước tái hiện:** `uv run python script/run_corruption_flow.py`
- **Nguyên nhân gốc:** Tần suất gửi request liên tục vượt quá giới hạn nạp token/phút (TPM/RPM) của API Key.
- **Cách xử lý:** Thêm cơ chế Exponential BackoffRetry loop và pacing sleep `time.sleep(0.2)` trong hàm `_judge_answer()` của `src/evaluation/metrics.py`.
- **Cách xác minh sau khi sửa:** Đã chạy thông suốt 100% cả 3 pha (Baseline, Corrupted, Repaired) với 180 lượt đánh giá OpenAI AI thành công.
- **Bài học kỹ thuật:** Các dịch vụ AI bên thứ ba luôn đòi hỏi cơ chế Retry & Rate Limiting chuyên biệt để đảm bảo độ tin cậy của Data Pipeline.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index:** REST API -> `crossref_records.json` -> `cleaning.py` -> `papers_clean.csv` -> `MiniLMEmbeddings` -> ChromaDB Collection.
2. **Evaluation set và ground-truth document IDs:** Bộ câu hỏi kiểm thử `test_set.json` lưu giữ thông tin `ground_truth_doc_ids` chính xác để đo tỷ lệ truất xuất đúng (`retrieval_hit_rate`) và Token F1.
3. **Quality checks khác freshness monitoring:** Quality checks kiểm tra tính toàn vẹn (Completeness/Uniqueness) của dữ liệu ngay sau khi làm sạch. Freshness monitoring kiểm tra độ tươi mới tính theo mốc thời gian xuất bản so với ngưỡng quy định (180 ngày).
4. **Vì sao phải dùng cùng test set:** Để đảm bảo tính công bằng của hệ quy chiếu (Apples-to-Apples Comparison). Nếu câu hỏi thay đổi giữa các pha, biến động điểm số sẽ bị nhiễu do độ khó của câu hỏi thay đổi thay vì phản ảnh chất lượng dữ liệu.
5. **Repair thành công dựa vào:** Sự gia tăng trở lại của các chỉ số RAG (`retrieval_hit_rate` = 1.0000, `mean_token_f1` = 0.9554) và các bài test Quality Check quay lại trạng thái `PASS`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | **`1.0000`** | **`0.6833`** | **`1.0000`** | Giảm 31.7% khi bị mất bài & cắt tiêu đề ➔ Phục hồi 100% |
| `mean_token_f1`      | **`0.9554`** | **`0.4891`** | **`0.9554`** | Giảm 46.6% xuống dưới 0.50 do tóm tắt nhiễu ➔ Phục hồi 100% |
| `judge_accuracy`     | **`0.9667`** | **`0.5167`** | **`0.9667`** | AI chấm rớt 45.0% do thiếu ngữ cảnh ➔ Phục hồi 100% |
| `mean_judge_score`   | **`4.8667`** | **`3.1000`** | **`4.8667`** | Điểm chất lượng AI rớt gần 1.8 điểm ➔ Phục hồi 100% |
| Quality checks         | `PASS` | `FAIL` | `PASS` | Phát hiện 4 dòng trùng & 8 dòng cũ ➔ Phục hồi PASS |
| Freshness status       | `Fresh` | `Stale` | `Fresh` | Phát hiện dữ liệu lỗi thời ➔ Phục hồi Fresh |

### Kết luận từ số liệu

1. **Compound Corruption ➔ Suy giảm chỉ số Agent**: Khi phá hoại 35-40% dữ liệu tóm tắt và xóa 6 bài báo mới nhất, chất lượng vector embedding ChromaDB bị sai lệch làm `retrieval_hit_rate` rớt xuống 0.6833 và `mean_token_f1` rớt xuống 0.4891.
2. **Data Repair ➔ Phục hồi hoàn hảo 100%**: Khi tái dựng lại từ Raw JSON Snapshot `crossref_records.json`, dữ liệu sạch được nạp lại và ChromaDB Vector Index được làm tươi, đưa toàn bộ chỉ số RAG và Data Quality Check trở lại mốc 100% tuyệt đối.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Dữ liệu đầu vào quyết định 90% chất lượng của RAG Agent (Garbage in, Garbage out).
2. Quy trình Data Observability & Monitoring giúp phát hiện sớm các sự cố trôi dạt dữ liệu (Data Drift) trước khi gây hại cho ứng dụng AI end-user.
3. Nguyên tắc Lưu trữ Raw Snapshot thô (Immutable Raw Layer) là chốt chặn quan trọng nhất để giúp khôi phục hệ thống khi xảy ra sự cố.

### Nếu có thêm thời gian

Mở rộng hạ tầng thử nghiệm lên 1.000 bài báo Crossref và triển khai luồng tự động khôi phục tự động (Automated Self-Healing Pipeline) thông qua Airflow / Cloud Composer.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Nguyễn Khánh Minh
**Ngày xác nhận:** 2026-08-06
