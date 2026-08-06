from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from core.utils import now_utc, write_json
from ingestion.cleaning import build_text_for_embedding

# --- Constants (khong hard-code so trong than ham) ---------------------------
SEED = 42
DROP_LATEST_N = 3
BLANK_SUMMARY_FRACTION = 0.25
NOISE_FRACTION = 0.20
TRUNCATE_TITLE_FRACTION = 0.20
TRUNCATE_TITLE_CHARS = 15
STALE_FRACTION = 0.30
STALE_SHIFT_DAYS_RANGE = (500, 900)
DUPLICATE_ROWS = 3

NOISE_TOKENS = [
    "lorem ipsum ###",
    "<jats:p>&&&</jats:p>",
    "AAAAAAAAAAAA",
    "??? ??? ???",
    "[[ENCODING ERROR]] ���",
]


def _count_from_fraction(total: int, fraction: float) -> int:
    """It nhat 1 row neu dataframe khong rong."""
    if total <= 0:
        return 0
    return max(1, int(round(total * fraction)))


def _pick(rng: np.random.Generator, index: pd.Index, size: int) -> list:
    size = min(size, len(index))
    if size <= 0:
        return []
    chosen = rng.choice(np.asarray(index), size=size, replace=False)
    return list(chosen)


def _parse_iso_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _log_entry(
    step: str,
    description: str,
    affected_paper_ids: list[str],
    row_count_before: int,
    row_count_after: int,
) -> dict:
    return {
        "step": step,
        "description": description,
        "affected_paper_ids": [str(pid) for pid in affected_paper_ids],
        "affected_rows": len(affected_paper_ids),
        "row_count_before": row_count_before,
        "row_count_after": row_count_after,
    }


def _inject_noise(summary: str, rng: np.random.Generator) -> str:
    """Chen 2 token rac vao giua summary (hoac noi duoi neu summary qua ngan)."""
    tokens = [NOISE_TOKENS[int(i)] for i in rng.choice(len(NOISE_TOKENS), size=2, replace=False)]
    text = summary or ""
    if len(text) < 40:
        return " ".join([text, *tokens]).strip()
    mid = len(text) // 2
    return f"{text[:mid]} {tokens[0]} {tokens[1]} {text[mid:]}"


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate nhieu dang data corruption tren cleaned dataframe.

    1. Drop latest records          -> retrieval_hit_rate, freshness
    2. Blank summary                -> quality check summary_length
    3. Inject noise vao summary     -> chat luong embedding / judge score
    4. Truncate title               -> exact-title lookup fail
    5. Stale publication date       -> quality check freshness
    6. Duplicate rows               -> quality check paper_id_valid
    7. Rebuild text_for_embedding + summary_chars + age_days
    8. Ghi corruption log ra output_log_path

    Deterministic voi SEED co dinh, khong mutate `df` goc.
    """
    rng = np.random.default_rng(SEED)
    work = df.copy(deep=True)
    rows_before_all = len(work)
    log: list[dict] = []

    if work.empty:
        write_json(
            Path(output_log_path),
            {
                "generated_at": now_utc().isoformat(),
                "seed": SEED,
                "rows_before": 0,
                "rows_after": 0,
                "steps": [],
            },
        )
        return work

    reference_date = now_utc().date()

    # --- 1. Drop latest records ----------------------------------------------
    # df baseline da sort published desc -> head(N) chinh la cac paper moi nhat.
    before = len(work)
    dropped = work.head(DROP_LATEST_N)
    dropped_ids = dropped["paper_id"].tolist()
    work = work.drop(index=dropped.index)
    log.append(
        _log_entry(
            "drop_latest",
            f"Xóa {len(dropped_ids)} bài báo mới nhất (sắp xếp theo ngày xuất bản giảm dần), "
            "mô phỏng việc mất dữ liệu ở lần đồng bộ gần nhất.",
            dropped_ids,
            before,
            len(work),
        )
    )

    # Cac scenario 2-5 chon row disjoint tren phan con lai.
    pool = pd.Index(work.index)
    n_blank = _count_from_fraction(len(pool), BLANK_SUMMARY_FRACTION)
    n_noise = _count_from_fraction(len(pool), NOISE_FRACTION)
    n_trunc = _count_from_fraction(len(pool), TRUNCATE_TITLE_FRACTION)
    n_stale = _count_from_fraction(len(pool), STALE_FRACTION)

    blank_idx = _pick(rng, pool, n_blank)
    pool = pool.drop(blank_idx)
    noise_idx = _pick(rng, pool, n_noise)
    pool = pool.drop(noise_idx)
    # Truncate title va stale date co the ap len row da bi blank/noise (doc lap cot),
    # nen chon lai tren toan bo index hien tai.
    trunc_idx = _pick(rng, pd.Index(work.index), n_trunc)
    stale_pool = pd.Index(work.index)
    stale_idx = _pick(rng, stale_pool, n_stale)

    # --- 2. Blank summary -----------------------------------------------------
    before = len(work)
    work.loc[blank_idx, "summary"] = ""
    work.loc[blank_idx, "summary_chars"] = 0
    log.append(
        _log_entry(
            "blank_summary",
            f"Xóa trắng phần tóm tắt của {len(blank_idx)} dòng "
            f"(khoảng {BLANK_SUMMARY_FRACTION:.0%} dữ liệu), mô phỏng trường bị thiếu khi trích xuất.",
            work.loc[blank_idx, "paper_id"].tolist(),
            before,
            len(work),
        )
    )

    # --- 3. Inject noise vao summary -----------------------------------------
    before = len(work)
    for idx in noise_idx:
        work.at[idx, "summary"] = _inject_noise(str(work.at[idx, "summary"] or ""), rng)
    log.append(
        _log_entry(
            "noise_summary",
            f"Chèn ký tự nhiễu và thẻ HTML sót lại vào phần tóm tắt của {len(noise_idx)} dòng "
            f"(khoảng {NOISE_FRACTION:.0%} dữ liệu), mô phỏng lỗi làm sạch và lỗi mã hóa ký tự.",
            work.loc[noise_idx, "paper_id"].tolist(),
            before,
            len(work),
        )
    )

    # --- 4. Truncate title ----------------------------------------------------
    before = len(work)
    for idx in trunc_idx:
        work.at[idx, "title"] = str(work.at[idx, "title"] or "")[:TRUNCATE_TITLE_CHARS]
    log.append(
        _log_entry(
            "truncate_title",
            f"Cắt tiêu đề còn {TRUNCATE_TITLE_CHARS} ký tự đầu ở {len(trunc_idx)} dòng, "
            "mô phỏng lỗi giới hạn độ dài cột khi ghi dữ liệu.",
            work.loc[trunc_idx, "paper_id"].tolist(),
            before,
            len(work),
        )
    )

    # --- 5. Stale publication date -------------------------------------------
    before = len(work)
    low, high = STALE_SHIFT_DAYS_RANGE
    for idx in stale_idx:
        published = _parse_iso_date(work.at[idx, "published"])
        if published is None:
            continue
        shift = int(rng.integers(low, high + 1))
        stale_date = published - timedelta(days=shift)
        work.at[idx, "published"] = stale_date.isoformat()
        work.at[idx, "updated"] = stale_date.isoformat()
    log.append(
        _log_entry(
            "stale_published",
            f"Lùi ngày xuất bản về quá khứ {low}–{high} ngày ở {len(stale_idx)} dòng "
            f"(khoảng {STALE_FRACTION:.0%} dữ liệu), mô phỏng dữ liệu cũ không được cập nhật.",
            work.loc[stale_idx, "paper_id"].tolist(),
            before,
            len(work),
        )
    )

    # --- 6. Duplicate rows ----------------------------------------------------
    before = len(work)
    dup_idx = _pick(rng, pd.Index(work.index), DUPLICATE_ROWS)
    duplicates = work.loc[dup_idx].copy()
    work = pd.concat([work, duplicates], ignore_index=False)
    log.append(
        _log_entry(
            "duplicate_rows",
            f"Nhân đôi {len(dup_idx)} dòng và giữ nguyên `paper_id`, mô phỏng lỗi nạp dữ liệu "
            "trùng lặp do chạy lại pipeline.",
            duplicates["paper_id"].tolist(),
            before,
            len(work),
        )
    )

    # --- 7. Rebuild derived columns ------------------------------------------
    work = work.reset_index(drop=True)
    work["summary"] = work["summary"].fillna("").astype(str)
    work["title"] = work["title"].fillna("").astype(str)
    work["summary_chars"] = work["summary"].str.len()

    ages: list[int] = []
    for value in work["published"]:
        published = _parse_iso_date(value)
        ages.append((reference_date - published).days if published else 0)
    work["age_days"] = ages

    work["text_for_embedding"] = [
        build_text_for_embedding(
            row["title"],
            row["summary"],
            str(row.get("authors_joined") or ""),
            str(row.get("categories_joined") or ""),
        )
        for _, row in work.iterrows()
    ]
    log.append(
        _log_entry(
            "rebuild_derived_fields",
            "Tính lại các cột dẫn xuất `summary_chars`, `age_days` và `text_for_embedding` "
            "trên toàn bộ dữ liệu sau khi gây lỗi.",
            [],
            len(work),
            len(work),
        )
    )

    # --- 8. Ghi corruption log ------------------------------------------------
    write_json(
        Path(output_log_path),
        {
            "generated_at": now_utc().isoformat(),
            "seed": SEED,
            "rows_before": rows_before_all,
            "rows_after": len(work),
            "config": {
                "drop_latest_n": DROP_LATEST_N,
                "blank_summary_fraction": BLANK_SUMMARY_FRACTION,
                "noise_fraction": NOISE_FRACTION,
                "truncate_title_fraction": TRUNCATE_TITLE_FRACTION,
                "truncate_title_chars": TRUNCATE_TITLE_CHARS,
                "stale_fraction": STALE_FRACTION,
                "stale_shift_days_range": list(STALE_SHIFT_DAYS_RANGE),
                "duplicate_rows": DUPLICATE_ROWS,
            },
            "steps": log,
        },
    )

    # Khong sort lai -> giu dau vet corruption.
    return work
