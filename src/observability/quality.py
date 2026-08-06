from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json
from ingestion.cleaning import MIN_SUMMARY_CHARS

# Neu hon nua so dong bi stale thi coi la fail check freshness.
STALE_FRACTION_TOLERANCE = 0.5
# Neu hon nua so dong co summary qua ngan thi coi la fail check summary length.
SHORT_SUMMARY_FRACTION_TOLERANCE = 0.5


def _check_row_count(df: pd.DataFrame) -> dict[str, Any]:
    row_count = int(len(df))
    return {
        "name": "row_count",
        "success": row_count > 0,
        "details": {"row_count": row_count},
    }


def _check_paper_id(df: pd.DataFrame) -> dict[str, Any]:
    if "paper_id" not in df.columns:
        return {"name": "paper_id_valid", "success": False, "details": {"reason": "missing paper_id column"}}
    non_null = df["paper_id"].notna() & (df["paper_id"].astype(str).str.strip() != "")
    null_count = int((~non_null).sum())
    duplicate_count = int(df.loc[non_null, "paper_id"].duplicated().sum())
    success = null_count == 0 and duplicate_count == 0
    return {
        "name": "paper_id_valid",
        "success": success,
        "details": {"null_or_empty": null_count, "duplicates": duplicate_count},
    }


def _check_title(df: pd.DataFrame) -> dict[str, Any]:
    if "title" not in df.columns:
        return {"name": "title_not_null", "success": False, "details": {"reason": "missing title column"}}
    non_null = df["title"].notna() & (df["title"].astype(str).str.strip() != "")
    null_count = int((~non_null).sum())
    return {
        "name": "title_not_null",
        "success": null_count == 0,
        "details": {"null_or_empty": null_count},
    }


def _check_summary_length(df: pd.DataFrame) -> dict[str, Any]:
    if "summary" not in df.columns:
        return {"name": "summary_length", "success": False, "details": {"reason": "missing summary column"}}
    total = len(df)
    lengths = df["summary"].fillna("").astype(str).str.len()
    short_count = int((lengths < MIN_SUMMARY_CHARS).sum())
    short_fraction = short_count / total if total else 1.0
    return {
        "name": "summary_length",
        "success": short_fraction <= SHORT_SUMMARY_FRACTION_TOLERANCE,
        "details": {
            "min_chars_threshold": MIN_SUMMARY_CHARS,
            "short_rows": short_count,
            "short_fraction": round(short_fraction, 4),
        },
    }


def _check_freshness(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    if "age_days" not in df.columns:
        return {"name": "freshness", "success": False, "details": {"reason": "missing age_days column"}}
    total = len(df)
    ages = pd.to_numeric(df["age_days"], errors="coerce")
    stale_count = int((ages > settings.freshness_threshold_days).sum())
    missing_count = int(ages.isna().sum())
    stale_fraction = stale_count / total if total else 1.0
    return {
        "name": "freshness",
        "success": missing_count == 0 and stale_fraction <= STALE_FRACTION_TOLERANCE,
        "details": {
            "freshness_threshold_days": settings.freshness_threshold_days,
            "stale_rows": stale_count,
            "stale_fraction": round(stale_fraction, 4),
            "missing_age_days": missing_count,
        },
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay bo data quality checks tren cleaned dataframe.

    1. Check row count.
    2. Check `paper_id` not null va unique.
    3. Check `title` not null.
    4. Check do dai `summary`.
    5. Check freshness bang `age_days`.
    6. Ghi ket qua vao `data/quality/`.
    """
    checks = [
        _check_row_count(df),
        _check_paper_id(df),
        _check_title(df),
        _check_summary_length(df),
        _check_freshness(df, settings),
    ]
    report = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "row_count": int(len(df)),
        "checks": checks,
        "success": all(check["success"] for check in checks),
    }

    output_path = settings.paths.quality_dir / f"{report_name}_quality.json"
    write_json(output_path, report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report.

    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - is_fresh
    4. Ghi JSON report.
    """
    total_rows = int(len(df))
    if total_rows == 0 or "published" not in df.columns:
        payload = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": total_rows,
            "is_fresh": False,
            "freshness_threshold_days": settings.freshness_threshold_days,
        }
        write_json(report_path, payload)
        return payload

    published = pd.to_datetime(df["published"], errors="coerce")
    ages = pd.to_numeric(df["age_days"], errors="coerce") if "age_days" in df.columns else None
    stale_rows = int((ages > settings.freshness_threshold_days).sum()) if ages is not None else 0

    payload = {
        "latest_published": published.max().date().isoformat() if published.notna().any() else None,
        "oldest_published": published.min().date().isoformat() if published.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "is_fresh": stale_rows == 0,
        "freshness_threshold_days": settings.freshness_threshold_days,
    }
    write_json(report_path, payload)
    return payload
