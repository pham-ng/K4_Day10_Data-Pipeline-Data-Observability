from __future__ import annotations

import sys
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pandas as pd
import pytest

from core.config import load_settings
from ingestion.cleaning import build_clean_dataframe, build_text_for_embedding
from ingestion.corruption import corrupt_clean_dataframe
from observability.quality import run_data_quality_checks, build_freshness_report
from collections import Counter
from core.utils import normalize_whitespace


def _token_f1(reference: str, prediction: str) -> float:
    ref_tokens = normalize_whitespace(reference).lower().split()
    pred_tokens = normalize_whitespace(prediction).lower().split()
    if not ref_tokens or not pred_tokens:
        return 0.0
    common = Counter(ref_tokens) & Counter(pred_tokens)
    common_count = sum(common.values())
    if common_count == 0:
        return 0.0
    precision = common_count / len(pred_tokens)
    recall = common_count / len(ref_tokens)
    return float(2 * precision * recall / (precision + recall))


def test_build_text_for_embedding():
    title = "AI Force Control"
    summary = "Safe interaction control."
    authors = "Vishal Khanna"
    text = build_text_for_embedding(title, summary, authors, "")
    assert "AI Force Control" in text
    assert "Safe interaction control." in text
    assert "Authors: Vishal Khanna" in text


def test_token_f1_exact_match():
    reference = "Human Robot Interaction"
    prediction = "human robot interaction"
    f1 = _token_f1(reference, prediction)
    assert f1 == 1.0


def test_token_f1_partial_match():
    reference = "Safe and intuitive human robot interaction"
    prediction = "Safe human robot interaction"
    f1 = _token_f1(reference, prediction)
    assert 0.70 < f1 < 1.0


def test_quality_checks_pass_on_clean_data(tmp_path):
    settings = load_settings()
    clean_df = pd.DataFrame(
        [
            {
                "paper_id": "10.1000/1",
                "title": "Title 1",
                "summary": "This is a valid summary with sufficient length.",
                "published": "2028-01-01",
                "age_days": 0,
            },
            {
                "paper_id": "10.1000/2",
                "title": "Title 2",
                "summary": "Another valid summary for paper 2 testing.",
                "published": "2028-02-01",
                "age_days": 0,
            },
        ]
    )
    report = run_data_quality_checks(clean_df, settings=settings, report_name="test_baseline")
    assert report["success"] is True


def test_corruption_triggers_quality_failures(tmp_path):
    settings = load_settings()
    clean_df = pd.DataFrame(
        [
            {
                "paper_id": f"10.1000/{i}",
                "title": f"Title paper number {i}",
                "summary": f"Detailed summary description for scientific paper number {i}.",
                "published": "2028-06-15",
                "age_days": 0,
            }
            for i in range(24)
        ]
    )
    corrupted_df = corrupt_clean_dataframe(clean_df, output_log_path=tmp_path / "log.json")
    assert len(corrupted_df) > 0
    report = run_data_quality_checks(corrupted_df, settings=settings, report_name="test_corrupted")
    # Duplicate rows scenario should fail paper_id_valid
    assert report["success"] is False
