from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import now_utc, write_text


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _checks_table(checks: list[dict[str, Any]]) -> str:
    lines = ["| Check | Status | Details |", "| --- | --- | --- |"]
    for check in checks:
        status = "PASS" if check.get("success") else "FAIL"
        lines.append(f"| {check.get('name')} | {status} | `{check.get('details')}` |")
    return "\n".join(lines)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase.

    1. Gom source summary.
    2. In metrics retrieval/evaluation.
    3. In data quality va freshness.
    4. Ghi markdown vao report_path.
    """
    ragas = metrics.get("ragas", {})
    ragas_lines = "\n".join(f"- **{k}**: {_fmt(v)}" for k, v in ragas.items()) if isinstance(ragas, dict) else str(ragas)

    lines = [
        "# Phase 1 Baseline Report",
        "",
        f"Generated at: {now_utc().isoformat()}",
        "",
        "## Source",
        "",
        f"- **API**: {source_summary.get('source_api')}",
        f"- **Query**: {source_summary.get('source_query')}",
        f"- **Filter**: {source_summary.get('source_filter')}",
        f"- **Raw records**: {source_summary.get('raw_records')}",
        f"- **Clean records**: {source_summary.get('clean_records')}",
        "",
        "## Evaluation Metrics",
        "",
        f"- **Samples**: {metrics.get('samples')}",
        f"- **Retrieval hit rate**: {_fmt(metrics.get('retrieval_hit_rate'))}",
        f"- **Mean token F1**: {_fmt(metrics.get('mean_token_f1'))}",
        f"- **Judge accuracy**: {_fmt(metrics.get('judge_accuracy'))}",
        f"- **Mean judge score**: {_fmt(metrics.get('mean_judge_score'))}",
        "- **Ragas**:",
        ragas_lines if ragas_lines else "- (none)",
        "",
        "## Data Quality",
        "",
        f"Overall: **{'PASS' if quality.get('success') else 'FAIL'}** ({quality.get('row_count')} rows)",
        "",
        _checks_table(quality.get("checks", [])),
        "",
        "## Freshness",
        "",
        f"- **Latest published**: {freshness.get('latest_published')}",
        f"- **Oldest published**: {freshness.get('oldest_published')}",
        f"- **Stale rows**: {freshness.get('stale_rows')} / {freshness.get('total_rows')}",
        f"- **Freshness threshold (days)**: {freshness.get('freshness_threshold_days')}",
        f"- **Is fresh**: {'YES' if freshness.get('is_fresh') else 'NO'}",
        "",
    ]
    write_text(report_path, "\n".join(lines))


COMPARE_METRICS = [
    ("retrieval_hit_rate", "Retrieval hit rate"),
    ("mean_token_f1", "Mean token F1"),
    ("judge_accuracy", "Judge accuracy"),
    ("mean_judge_score", "Mean judge score"),
]

CHECK_NAMES = [
    "row_count",
    "paper_id_valid",
    "title_not_null",
    "summary_length",
    "freshness",
]

# Repaired duoc coi la "phuc hoi" neu dat >= 95% baseline.
RECOVERY_TOLERANCE = 0.95


def _delta(new: Any, base: Any) -> str:
    """Chuoi delta co dau, `n/a` neu thieu gia tri."""
    if not isinstance(new, (int, float)) or not isinstance(base, (int, float)):
        return "n/a"
    return f"{new - base:+.4f}"


def _status(flag: Any) -> str:
    return "PASS" if flag else "FAIL"


def _corruption_table(corruption_log: dict[str, Any] | None) -> str:
    if not corruption_log:
        return "_(Không tìm thấy `corruption_log.json`.)_"
    steps = corruption_log.get("steps", [])
    if not steps:
        return "_(Corruption log rỗng, chưa có kịch bản nào được ghi nhận.)_"
    lines = [
        "| Kịch bản | Mô tả | Số dòng bị ảnh hưởng | Số dòng trước | Số dòng sau |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in steps:
        lines.append(
            f"| `{step.get('step')}` | {step.get('description')} | {step.get('affected_rows')} "
            f"| {step.get('row_count_before')} | {step.get('row_count_after')} |"
        )
    return "\n".join(lines)


def _metrics_matrix(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
) -> str:
    lines = [
        "| Chỉ số | Baseline | Corrupted | Repaired | Chênh lệch (corrupted − baseline) "
        "| Chênh lệch (repaired − baseline) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for key, label in COMPARE_METRICS:
        b, c, r = baseline.get(key), corrupted.get(key), repaired.get(key)
        lines.append(
            f"| {label} | {_fmt(b)} | {_fmt(c)} | {_fmt(r)} | {_delta(c, b)} | {_delta(r, b)} |"
        )
    return "\n".join(lines)


def _checks_matrix(reports: list[tuple[str, dict[str, Any]]]) -> str:
    """Gop nhieu quality report theo ten check thanh mot bang."""
    indexed = [
        (label, {check.get("name"): check for check in (report or {}).get("checks", [])})
        for label, report in reports
    ]
    header = "| Kiểm tra | " + " | ".join(label for label, _ in indexed) + " |"
    lines = [header, "| --- |" + " --- |" * len(indexed)]

    names: list[str] = list(CHECK_NAMES)
    for _, by_name in indexed:
        for name in by_name:
            if name not in names:
                names.append(name)

    for name in names:
        cells = []
        for _, by_name in indexed:
            check = by_name.get(name)
            cells.append(_status(check.get("success")) if check else "n/a")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    overall = [_status((report or {}).get("success")) for _, report in reports]
    lines.append("| **Tổng kết** | " + " | ".join(f"**{value}**" for value in overall) + " |")
    return "\n".join(lines)


def _freshness_matrix(reports: list[tuple[str, dict[str, Any]]]) -> str:
    header = "| Chỉ tiêu | " + " | ".join(label for label, _ in reports) + " |"
    lines = [header, "| --- |" + " --- |" * len(reports)]
    rows = [
        ("Ngày xuất bản mới nhất", lambda r: r.get("latest_published")),
        ("Ngày xuất bản cũ nhất", lambda r: r.get("oldest_published")),
        ("Số dòng quá hạn / tổng số dòng", lambda r: f"{r.get('stale_rows')} / {r.get('total_rows')}"),
        ("Dữ liệu còn mới", lambda r: "CÓ" if r.get("is_fresh") else "KHÔNG"),
    ]
    for label, getter in rows:
        cells = [str(getter(report or {})) for _, report in reports]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _conclusion_lines(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
) -> list[str]:
    """Sinh ket luan tu so lieu thuc te, khong viet cung."""
    lines: list[str] = []
    base_hit = baseline.get("retrieval_hit_rate")
    corrupt_hit = corrupted.get("retrieval_hit_rate")
    repair_hit = repaired.get("retrieval_hit_rate")

    if isinstance(base_hit, (int, float)) and isinstance(corrupt_hit, (int, float)):
        if corrupt_hit < base_hit:
            drop_pct = (base_hit - corrupt_hit) / base_hit * 100 if base_hit else 0.0
            lines.append(
                "- **Dữ liệu lỗi làm giảm chất lượng của agent**: tỷ lệ truy hồi đúng tài liệu "
                f"(retrieval hit rate) giảm từ {_fmt(base_hit)} xuống {_fmt(corrupt_hit)}, "
                f"tương đương giảm {drop_pct:.1f}% so với baseline."
            )
        else:
            lines.append(
                "- **Cảnh báo**: tỷ lệ truy hồi đúng tài liệu của bộ dữ liệu lỗi không giảm so với "
                f"baseline ({_fmt(corrupt_hit)} so với {_fmt(base_hit)}). Cần tăng mức độ phá dữ liệu "
                "bằng cách nâng `DROP_LATEST_N` hoặc các tham số tỷ lệ trong "
                "`src/ingestion/corruption.py`."
            )
    else:
        lines.append(
            "- Không đủ số liệu `retrieval_hit_rate` để kết luận về ảnh hưởng của dữ liệu lỗi."
        )

    if isinstance(base_hit, (int, float)) and isinstance(repair_hit, (int, float)):
        if repair_hit >= base_hit * RECOVERY_TOLERANCE:
            lines.append(
                "- **Việc sửa dữ liệu đã khôi phục chất lượng**: tỷ lệ truy hồi đúng tài liệu quay "
                f"lại mức {_fmt(repair_hit)}, đạt tối thiểu {RECOVERY_TOLERANCE:.0%} so với baseline "
                f"({_fmt(base_hit)})."
            )
        else:
            lines.append(
                f"- **Cảnh báo**: bộ dữ liệu đã sửa mới đạt {_fmt(repair_hit)}, chưa tới "
                f"{RECOVERY_TOLERANCE:.0%} baseline ({_fmt(base_hit)}). Cần kiểm tra lại bước dựng "
                "lại dữ liệu từ nguồn thô."
            )

    # Cac metric con lai.
    for key, label in COMPARE_METRICS[1:]:
        b, c, r = baseline.get(key), corrupted.get(key), repaired.get(key)
        if isinstance(b, (int, float)) and isinstance(c, (int, float)) and isinstance(r, (int, float)):
            lines.append(
                f"- {label}: baseline {_fmt(b)} → dữ liệu lỗi {_fmt(c)} → dữ liệu đã sửa {_fmt(r)}."
            )

    lines.append(
        "- Kết quả kiểm tra chất lượng dữ liệu: bộ dữ liệu lỗi "
        f"**{_status(corrupted_quality.get('success'))}**, bộ dữ liệu đã sửa "
        f"**{_status(repaired_quality.get('success'))}**."
    )
    lines.append(
        "- Lưu ý: cột `age_days` được tính theo ngày chạy pipeline, nên bộ dữ liệu đã sửa có thể "
        "không trùng khớp tuyệt đối với baseline. Đây là hành vi mong đợi, không phải lỗi."
    )
    return lines


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    corruption_log: dict[str, Any] | None = None,
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
    chart_path=None,
) -> None:
    """Viet markdown report so sanh baseline / corrupted / repaired.

    1. Header.
    2. Bang corruption scenarios (tu corruption_log.json).
    3. Bang metrics comparison + delta.
    4. Bang data quality comparison.
    5. Bang freshness comparison.
    6. Ket luan sinh tu so lieu.
    """
    quality_reports = [
        ("Baseline", baseline_quality or {}),
        ("Corrupted", corrupted_quality or {}),
        ("Repaired", repaired_quality or {}),
    ]
    freshness_reports = [
        ("Baseline", baseline_freshness or {}),
        ("Corrupted", corrupted_freshness or {}),
        ("Repaired", repaired_freshness or {}),
    ]

    lines = [
        "# Báo cáo ảnh hưởng của dữ liệu lỗi",
        "",
        f"Thời điểm tạo báo cáo: {now_utc().isoformat()}",
        "",
        "Báo cáo so sánh ba bộ dữ liệu:",
        "",
        "- **Baseline** — dữ liệu sạch sau bước làm sạch ban đầu.",
        "- **Corrupted** — dữ liệu đã bị chèn lỗi có chủ đích để mô phỏng sự cố pipeline.",
        "- **Repaired** — dữ liệu được dựng lại từ nguồn thô để khắc phục các lỗi trên.",
        "",
        "Cả ba bộ dữ liệu được đánh giá trên cùng một tập câu hỏi kiểm thử, nhờ đó chênh lệch "
        "chỉ số phản ánh đúng tác động của chất lượng dữ liệu.",
        "",
        "## 1. Các kịch bản gây lỗi dữ liệu",
        "",
        _corruption_table(corruption_log),
        "",
        "## 2. Chỉ số đánh giá",
        "",
        _metrics_matrix(baseline_metrics, corrupted_metrics, repaired_metrics),
        "",
        f"Số câu hỏi đánh giá: baseline {baseline_metrics.get('samples')}, "
        f"corrupted {corrupted_metrics.get('samples')}, repaired {repaired_metrics.get('samples')}.",
        "",
        "## 3. Kiểm tra chất lượng dữ liệu",
        "",
        _checks_matrix(quality_reports),
        "",
        "## 4. Độ tươi mới của dữ liệu",
        "",
        _freshness_matrix(freshness_reports),
        "",
        "## 5. Kết luận",
        "",
        *_conclusion_lines(
            baseline_metrics,
            corrupted_metrics,
            repaired_metrics,
            corrupted_quality or {},
            repaired_quality or {},
        ),
        "",
    ]

    if chart_path is not None:
        lines.extend(
            [
                "## 6. Biểu đồ so sánh",
                "",
                f"![Biểu đồ so sánh chỉ số giữa ba bộ dữ liệu]({Path(chart_path).name})",
                "",
                "_Điểm `mean_judge_score` gốc nằm trên thang 1–5, đã được chia cho 5 để đưa về "
                "cùng thang 0–1 với các chỉ số còn lại._",
                "",
            ]
        )

    write_text(report_path, "\n".join(lines))


def render_metrics_chart(
    chart_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> bool:
    """Bonus: bar chart 4 metric x 3 dataset. Return False neu thieu matplotlib."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    labels = [label for _, label in COMPARE_METRICS]
    series = [
        ("Baseline", baseline_metrics),
        ("Corrupted", corrupted_metrics),
        ("Repaired", repaired_metrics),
    ]
    # mean_judge_score thang 1-5 -> chia 5 de cung thang do voi cac ty le 0-1.
    def _value(metrics: dict[str, Any], key: str) -> float:
        raw = metrics.get(key)
        if not isinstance(raw, (int, float)):
            return 0.0
        return raw / 5.0 if key == "mean_judge_score" else float(raw)

    positions = range(len(labels))
    width = 0.26
    fig, ax = plt.subplots(figsize=(9, 5))
    for offset, (name, metrics) in enumerate(series):
        values = [_value(metrics, key) for key, _ in COMPARE_METRICS]
        ax.bar([p + (offset - 1) * width for p in positions], values, width=width, label=name)

    ax.set_xticks(list(positions))
    ax.set_xticklabels(
        [f"{label}\n(scaled /5)" if label == "Mean judge score" else label for label in labels]
    )
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score (normalised 0-1)")
    ax.set_title("Baseline vs Corrupted vs Repaired")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = Path(chart_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True
