from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

MIN_DOCUMENTS = 3
DEFAULT_SAMPLE_SIZE = 20


def _build_questions_for_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    title = row["title"]
    paper_id = row["paper_id"]
    ground_truth_doc_ids = [paper_id]

    candidates: list[tuple[str, str, str]] = [
        ("summary", f"What is the paper '{title}' about?", first_sentence(row.get("summary", ""))),
        ("authors", f"Who authored '{title}'?", row.get("authors_joined", "")),
        ("date", f"When was '{title}' published?", row.get("published", "")),
        ("categories", f"What categories does '{title}' belong to?", row.get("categories_joined", "")),
    ]

    questions = []
    for question_type, question, ground_truth in candidates:
        ground_truth = (ground_truth or "").strip()
        if not ground_truth:
            continue
        questions.append(
            {
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": ground_truth_doc_ids,
            }
        )
    return questions


def build_test_set(df: pd.DataFrame, output_path, sample_size: int = DEFAULT_SAMPLE_SIZE) -> list[dict[str, Any]]:
    """Tao bo evaluation set tu cleaned dataframe.

    1. Kiem tra so luong document toi thieu.
    2. Chon mot so paper dai dien (top `sample_size` theo thu tu da sort trong df).
    3. Tao nhieu loai cau hoi: summary, authors, date, categories - khop voi
       pattern ma `retrieval/qa.py` dung de tra loi, de ground_truth so sanh duoc.
    4. Moi row co: id, question_type, question, ground_truth, ground_truth_doc_ids.
    5. Ghi file JSON vao output_path.
    """
    if df is None or df.empty:
        raise ValueError("Cannot build a test set from an empty dataframe.")
    if len(df) < MIN_DOCUMENTS:
        raise ValueError(f"Need at least {MIN_DOCUMENTS} clean documents to build a test set, got {len(df)}.")

    sample_df = df.head(sample_size)

    test_set: list[dict[str, Any]] = []
    counter = 0
    for row in sample_df.to_dict(orient="records"):
        for question in _build_questions_for_row(row):
            counter += 1
            question["id"] = f"q-{counter:04d}"
            test_set.append(question)

    if not test_set:
        raise ValueError("No valid questions could be generated from the cleaned dataframe.")

    # Reorder keys for readability: id first.
    test_set = [
        {
            "id": item["id"],
            "question_type": item["question_type"],
            "question": item["question"],
            "ground_truth": item["ground_truth"],
            "ground_truth_doc_ids": item["ground_truth_doc_ids"],
        }
        for item in test_set
    ]

    write_json(output_path, test_set)
    return test_set
