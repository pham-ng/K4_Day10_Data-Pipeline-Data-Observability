"""Render lai comparison report tu cac artifact JSON da co, khong chay lai evaluation.

Dung khi chi muon sua format report:

    uv run python script/run_comparison.py
"""

from __future__ import annotations

from core.config import load_settings
from core.utils import read_json
from observability.reporting import generate_corruption_report, render_metrics_chart


def _read_optional(path):
    return read_json(path) if path.exists() else None


def main() -> None:
    settings = load_settings()
    paths = settings.paths

    required = {
        "baseline_metrics": paths.baseline_metrics,
        "corrupted_metrics": paths.corrupted_metrics,
        "repaired_metrics": paths.repaired_metrics,
    }
    missing = [f"{name} ({path})" for name, path in required.items() if not path.exists()]
    if missing:
        raise RuntimeError(
            "Thieu metrics artifacts: " + ", ".join(missing) + ". Chay run_corruption_flow.py truoc."
        )

    baseline_metrics = read_json(paths.baseline_metrics)
    corrupted_metrics = read_json(paths.corrupted_metrics)
    repaired_metrics = read_json(paths.repaired_metrics)

    chart_path = paths.comparison_report.parent / "metrics_comparison.png"
    has_chart = render_metrics_chart(
        chart_path,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
    )

    generate_corruption_report(
        report_path=paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
        corrupted_quality=_read_optional(paths.quality_dir / "corrupted_quality.json") or {},
        repaired_quality=_read_optional(paths.quality_dir / "repaired_quality.json") or {},
        corrupted_freshness=_read_optional(paths.quality_dir / "corrupted_freshness.json") or {},
        repaired_freshness=_read_optional(paths.quality_dir / "repaired_freshness.json") or {},
        corruption_log=_read_optional(paths.corruption_log),
        baseline_quality=_read_optional(paths.quality_dir / "baseline_quality.json"),
        baseline_freshness=_read_optional(paths.freshness_report),
        chart_path=chart_path if has_chart else None,
    )
    print(f"[comparison] report -> {paths.comparison_report}", flush=True)
    if has_chart:
        print(f"[comparison] chart  -> {chart_path}", flush=True)
    else:
        print("[comparison] chart skipped (matplotlib chua duoc cai)", flush=True)


if __name__ == "__main__":
    main()
