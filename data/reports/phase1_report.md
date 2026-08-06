# Phase 1 Baseline Report

Generated at: 2026-08-06T12:26:30.185733+00:00

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

## Checkpoint C2 Theoretical Explanations

### 1. Tại sao bộ câu hỏi phải được chốt và đóng băng trước khi chạy các bước đánh giá RAG?
- **Nguyên tắc so sánh cùng hệ quy chiếu (Apples-to-Apples Comparison)**: Để đánh giá chính xác tác động của lỗi dữ liệu (Data Corruption) và khôi phục dữ liệu (Repair), chúng ta bắt buộc phải kiểm thử 3 trạng thái hệ thống (Baseline vs Corrupted vs Repaired) trên cùng một bộ đề thi cố định.
- Nếu mỗi pha lại tạo một bộ câu hỏi mới, sự biến động điểm số sẽ bị nhiễu do độ khó/dễ của câu hỏi khác nhau, khiến kết quả so sánh không còn ý nghĩa khoa học.

### 2. Xử lý thế nào nếu một bài báo trong ground_truth_doc_ids bị thiếu ở pha sau (ví dụ khi bị Corrupt xóa mất)?
- **Giữ nguyên câu hỏi trong Eval Set, KHÔNG xóa hay sửa câu hỏi**: Mục đích của thử nghiệm phá hoại dữ liệu (Data Corruption) là đo lường mức độ suy giảm hiệu năng khi xảy ra sự cố mất dữ liệu.
- Khi bài báo bị xóa khỏi CSDL Vector Store ở pha Corrupted, Retriever sẽ không tìm thấy bài báo đó (`retrieval_hit_rate` của câu hỏi rơi về 0.0), làm sụt giảm điểm F1 và Judge Score toàn hệ thống. Điều này phản ánh đúng thực tế vận hành: Mất dữ liệu nguồn sẽ khiến Agent trả lời sai hoặc không tìm ra đáp án.

## Checkpoint C3 Theoretical Explanations

### 1. Chỉ số retrieval_hit_rate phản ánh hiệu suất của cấu phần nào?
- Chỉ số **retrieval_hit_rate** phản ánh trực tiếp hiệu suất của cấu phần **Retriever (Bộ truy xuất ngữ cảnh)**, bao gồm mô hình **Embedding** (`sentence-transformers/all-MiniLM-L6-v2`) và **Vector Database** (`ChromaDB`).
- Nó đo lường tỷ lệ các câu hỏi mà Vector Search tìm kiếm đúng tài liệu chứa đáp án (`ground_truth_doc_ids`) để làm Context đưa vào LLM.

### 2. Tại sao điểm Token F1 của câu trả lời lại không bao giờ đạt tuyệt đối 1.0?
- **Khả năng diễn đạt tự nhiên (Paraphrasing)**: LLM khi trả lời thường tổng hợp và viết lại bằng câu văn tự nhiên (thêm từ nối, từ ngữ ngữ cảnh) thay vì trích xuất y nguyên từng từ trong ground truth.
- **Sự khác biệt cấu trúc từ ngữ & Stopwords**: Điểm Token F1 đo lường sự trùng lặp tập hợp từ ngữ ngắt lẻ (tokens). Sự xuất hiện của các từ nối bổ trợ khiến tỷ lệ trùng lặp tập hợp từ F1 bị giảm nhẹ (thường đạt khoảng 0.85 - 0.96). Do đó cần kết hợp thêm chỉ số **LLM Judge / Semantic Score** để đánh giá đúng độ chuẩn xác ngữ nghĩa.
