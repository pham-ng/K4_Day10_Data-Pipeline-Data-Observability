from __future__ import annotations

from datetime import date, datetime
import re

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

MIN_SUMMARY_CHARS = 20

# Crossref abstract thuong la JATS XML (vd <jats:p>...</jats:p>), can bo tag truoc khi dung.
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_markup(value: str) -> str:
    return _TAG_RE.sub(" ", value or "")


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def build_text_for_embedding(
    title: str,
    summary: str,
    authors_joined: str,
    categories_joined: str,
) -> str:
    """Cong thuc duy nhat de tao `text_for_embedding`.

    Dung chung boi `build_clean_dataframe` (clean) va `corruption` (rebuild sau khi corrupt)
    de tranh lech logic giua hai pipeline.
    """
    return normalize_whitespace(
        " ".join(
            part
            for part in [
                title or "",
                summary or "",
                f"Authors: {authors_joined}" if authors_joined else "",
                f"Categories: {categories_joined}" if categories_joined else "",
            ]
            if part
        )
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    1. Normalize title, summary, authors, categories.
    2. Parse published/updated date.
    3. Tinh age_days.
    4. Tao cot helper:
       - authors_joined
       - categories_joined
       - summary_chars
       - text_for_embedding
    5. Drop duplicates va filter row xau.
    6. Sort dataframe va return.
    """
    reference_date = run_date.date() if isinstance(run_date, datetime) else run_date

    rows: list[dict] = []
    for record in records:
        paper_id = normalize_whitespace(record.paper_id or "")
        title = normalize_whitespace(_strip_markup(record.title or ""))
        summary = normalize_whitespace(_strip_markup(record.summary or ""))

        # Invalid record: thieu id hoac title thi bo qua.
        if not paper_id or not title:
            continue

        published_date = _parse_date(record.published) or _parse_date(record.updated)
        if published_date is None:
            continue

        authors = [normalize_whitespace(a) for a in (record.authors or []) if a and a.strip()]
        categories = [normalize_whitespace(c) for c in (record.categories or []) if c and c.strip()]
        primary_category = normalize_whitespace(record.primary_category or "") or (
            categories[0] if categories else ""
        )

        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)
        summary_chars = len(summary)
        age_days = (reference_date - published_date).days

        text_for_embedding = build_text_for_embedding(
            title, summary, authors_joined, categories_joined
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "summary_chars": summary_chars,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": primary_category,
                "published": published_date.isoformat(),
                "updated": normalize_whitespace(record.updated or "") or published_date.isoformat(),
                "age_days": age_days,
                "abs_url": normalize_whitespace(record.abs_url or ""),
                "pdf_url": normalize_whitespace(record.pdf_url or ""),
                "comment": normalize_whitespace(record.comment or ""),
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.drop_duplicates(subset="paper_id", keep="first")
    df = df[df["title"].str.len() > 0]
    df = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df
