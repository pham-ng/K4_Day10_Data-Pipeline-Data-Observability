from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import requests
import time
from typing import Any

from core.config import Settings


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """TODO(student): parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    records = []

    if "message" not in payload or "items" not in payload["message"]:
        return records

    for item in payload["message"]["items"]:
        try:
            # Extract DOI (paper_id)
            doi = item.get("DOI", "").strip()
            if not doi:
                continue

            # Extract title
            title_list = item.get("title", [])
            title = title_list[0].strip() if title_list else ""
            if not title:
                continue

            # Extract abstract (summary)
            summary = item.get("abstract", "").strip()

            # Extract authors
            authors = []
            for author in item.get("author", []):
                name_parts = []
                if "given" in author:
                    name_parts.append(author["given"])
                if "family" in author:
                    name_parts.append(author["family"])
                if name_parts:
                    authors.append(" ".join(name_parts))

            # Extract categories (subject)
            categories = [cat.strip() for cat in item.get("subject", []) if cat.strip()]
            primary_category = categories[0] if categories else ""

            # Extract dates
            published = ""
            if "published" in item:
                date_parts = item["published"].get("date-parts", [[]])
                if date_parts and date_parts[0]:
                    year, month, day = (date_parts[0] + [1, 1])[:3]
                    published = f"{year:04d}-{month:02d}-{day:02d}"

            updated = published  # Crossref doesn't have updated, use published

            # Extract URLs
            abs_url = item.get("URL", "").strip() if item.get("URL") else ""
            pdf_url = ""

            # Extract comment (if available)
            comment = item.get("short-title", [""])[0] if "short-title" in item else ""

            record = PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment
            )
            records.append(record)
        except Exception as e:
            # Skip malformed records
            continue

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """TODO(student): goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    # Ensure raw directory exists
    settings.paths.raw_api_response.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.raw_records_json.parent.mkdir(parents=True, exist_ok=True)

    api_url = "https://api.crossref.org/works"
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "sort": "published",
        "order": "desc"
    }

    # Retry logic for rate limits
    max_retries = 3
    retry_count = 0
    payload = None

    while retry_count < max_retries:
        try:
            response = requests.get(
                api_url,
                params=params,
                headers={"User-Agent": "Lab-Pipeline/1.0"},
                timeout=30
            )

            if response.status_code == 200:
                payload = response.json()
                break
            elif response.status_code in [429, 503]:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count
                    time.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(f"API rate limited after {max_retries} retries")
            else:
                response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch from Crossref API: {str(e)}")

    if not payload:
        raise RuntimeError("Failed to fetch data from Crossref API")

    # Save raw response
    with open(settings.paths.raw_api_response, "w") as f:
        json.dump(payload, f, indent=2)

    # Parse records
    records = parse_crossref_payload(payload)

    # Save parsed records
    records_data = [
        {
            "paper_id": r.paper_id,
            "title": r.title,
            "summary": r.summary,
            "authors": r.authors,
            "categories": r.categories,
            "primary_category": r.primary_category,
            "published": r.published,
            "updated": r.updated,
            "abs_url": r.abs_url,
            "pdf_url": r.pdf_url,
            "comment": r.comment
        }
        for r in records
    ]

    with open(settings.paths.raw_records_json, "w") as f:
        json.dump(records_data, f, indent=2)

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """TODO(student): doc JSON snapshot va map thanh `PaperRecord`."""
    if not path.exists():
        return []

    with open(path, "r") as f:
        data = json.load(f)

    records = []
    for item in data:
        try:
            record = PaperRecord(
                paper_id=item.get("paper_id", ""),
                title=item.get("title", ""),
                summary=item.get("summary", ""),
                authors=item.get("authors", []),
                categories=item.get("categories", []),
                primary_category=item.get("primary_category", ""),
                published=item.get("published", ""),
                updated=item.get("updated", ""),
                abs_url=item.get("abs_url", ""),
                pdf_url=item.get("pdf_url", ""),
                comment=item.get("comment", "")
            )
            records.append(record)
        except Exception:
            continue

    return records
