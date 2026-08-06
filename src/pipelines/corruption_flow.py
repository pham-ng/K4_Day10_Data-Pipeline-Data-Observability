from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report, render_metrics_chart
from retrieval.index import LocalEmbeddingIndex

TOTAL_STEPS = 11


def _log(step: int, message: str) -> None:
    print(f"[corruption] step {step}/{TOTAL_STEPS}: {message}", flush=True)


def _info(message: str) -> None:
    print(f"[corruption]   {message}", flush=True)


def _fmt(value) -> str:
    return f"{value:.4f}" if isinstance(value, (int, float)) else str(value)


def _print_summary_table(
    baseline: dict,
    corrupted: dict,
    repaired: dict,
) -> None:
    metric_names = [
        "retrieval_hit_rate",
        "mean_token_f1",
        "judge_accuracy",
        "mean_judge_score",
    ]
    header = f"{'metric':<22}{'baseline':>12}{'corrupted':>12}{'repaired':>12}"
    print("[corruption] " + header, flush=True)
    print("[corruption] " + "-" * len(header), flush=True)
    for name in metric_names:
        row = (
            f"{name:<22}"
            f"{_fmt(baseline.get(name)):>12}"
            f"{_fmt(corrupted.get(name)):>12}"
            f"{_fmt(repaired.get(name)):>12}"
        )
        print("[corruption] " + row, flush=True)


def main() -> None:
    """Corruption -> evaluate -> repair -> compare flow.

     1. Load settings.
     2. Guard: baseline artifacts phai ton tai.
     3. Load baseline metrics + clean dataset.
     4. Corrupt dataset va save artifacts.
     5. Rebuild index + evaluate tren test set cu.
     6. Quality checks + freshness tren corrupted data.
     7. Repair: build lai clean dataframe tu raw records.
     8. Rebuild index + evaluate tren repaired data.
     9. Quality checks + freshness tren repaired data.
    10. Tao comparison report.
    11. In bang tom tat.
    """
    print("[corruption] === START ===", flush=True)

    # 1. Load settings.
    _log(1, "loading settings ...")
    settings = load_settings()
    paths = settings.paths
    _info(f"provider={settings.llm_provider} model={settings.model_name}")

    # 2. Guard.
    _log(2, "checking baseline artifacts ...")
    missing = [
        str(path)
        for path in (paths.clean_json, paths.baseline_metrics, paths.eval_testset)
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(
            "Thieu baseline artifacts: " + ", ".join(missing) + ". Chay run_phase1.py truoc."
        )

    # 3. Load baseline metrics + clean dataset.
    _log(3, "loading baseline metrics + clean dataset ...")
    baseline_metrics = read_json(paths.baseline_metrics)
    baseline_df = pd.DataFrame(read_json(paths.clean_json))
    if baseline_df.empty:
        raise RuntimeError("Baseline clean dataset rong; chay lai run_phase1.py.")
    _info(f"baseline rows={len(baseline_df)} retrieval_hit_rate={_fmt(baseline_metrics.get('retrieval_hit_rate'))}")

    # 4. Corrupt + save artifacts.
    _log(4, "corrupting dataset ...")
    corrupted_df = corrupt_clean_dataframe(baseline_df, paths.corruption_log)
    write_csv(corrupted_df, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    _info(f"corrupted rows={len(corrupted_df)} -> {paths.corrupted_clean_csv}")
    _info(f"corruption log -> {paths.corruption_log}")

    # 5. Rebuild index + evaluate (corrupted).
    _log(5, "building corrupted index + evaluating ...")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings=settings,
        embeddings_output_path=paths.corrupted_embeddings_json,
    )
    _info(f"collection={corrupted_index.collection_name} documents={len(corrupted_index.documents)}")
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=paths.eval_testset,  # dung lai test set cu, khong rebuild
        metrics_output_path=paths.corrupted_metrics,
        answers_output_path=paths.corrupted_answers,
    )
    _info(
        f"corrupted retrieval_hit_rate={_fmt(corrupted_bundle.summary['retrieval_hit_rate'])} "
        f"mean_token_f1={_fmt(corrupted_bundle.summary['mean_token_f1'])}"
    )

    # 6. Quality + freshness (corrupted).
    _log(6, "data quality + freshness (corrupted) ...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings=settings, report_name="corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings=settings,
        report_path=paths.quality_dir / "corrupted_freshness.json",
    )
    _info(
        f"quality_success={corrupted_quality.get('success')} is_fresh={corrupted_freshness.get('is_fresh')}"
    )

    # 7. Repair: tai tao tu raw source thay vi va corrupted df.
    _log(7, "repairing dataset from raw records ...")
    if settings.refresh_source:
        _info(f"fetching raw records from {settings.source_api} ...")
        records = fetch_source_records(settings)
    else:
        if not paths.raw_records_json.exists():
            raise RuntimeError(
                f"Khong tim thay {paths.raw_records_json}. Chay run_phase1.py hoac set REFRESH_SOURCE=1."
            )
        _info(f"loading cached raw records from {paths.raw_records_json}")
        records = load_raw_records(paths.raw_records_json)
    repaired_df = build_clean_dataframe(records, run_date=now_utc())
    if repaired_df.empty:
        raise RuntimeError("Repair tao ra dataframe rong; kiem tra raw source data.")
    write_csv(repaired_df, paths.repaired_clean_csv)
    write_json(paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    _info(f"repaired rows={len(repaired_df)} -> {paths.repaired_clean_csv}")

    # 8. Rebuild index + evaluate (repaired).
    _log(8, "building repaired index + evaluating ...")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings=settings,
        embeddings_output_path=paths.repaired_embeddings_json,
    )
    _info(f"collection={repaired_index.collection_name} documents={len(repaired_index.documents)}")
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.repaired_metrics,
        answers_output_path=paths.repaired_answers,
    )
    _info(
        f"repaired retrieval_hit_rate={_fmt(repaired_bundle.summary['retrieval_hit_rate'])} "
        f"mean_token_f1={_fmt(repaired_bundle.summary['mean_token_f1'])}"
    )

    # 9. Quality + freshness (repaired).
    _log(9, "data quality + freshness (repaired) ...")
    repaired_quality = run_data_quality_checks(repaired_df, settings=settings, report_name="repaired")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings=settings,
        report_path=paths.quality_dir / "repaired_freshness.json",
    )
    _info(
        f"quality_success={repaired_quality.get('success')} is_fresh={repaired_freshness.get('is_fresh')}"
    )

    # 10. Comparison report.
    _log(10, "writing comparison report ...")
    baseline_quality_path = paths.quality_dir / "baseline_quality.json"
    corruption_log = read_json(paths.corruption_log) if paths.corruption_log.exists() else None
    baseline_quality = read_json(baseline_quality_path) if baseline_quality_path.exists() else None
    baseline_freshness = read_json(paths.freshness_report) if paths.freshness_report.exists() else None

    chart_path = paths.comparison_report.parent / "metrics_comparison.png"
    has_chart = render_metrics_chart(
        chart_path,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
    )
    _info(f"chart -> {chart_path}" if has_chart else "chart skipped (matplotlib chua duoc cai)")

    generate_corruption_report(
        report_path=paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
        corruption_log=corruption_log,
        baseline_quality=baseline_quality,
        baseline_freshness=baseline_freshness,
        chart_path=chart_path if has_chart else None,
    )
    _info(f"report -> {paths.comparison_report}")

    # 11. Bang tom tat.
    _log(11, "summary")
    _print_summary_table(baseline_metrics, corrupted_bundle.summary, repaired_bundle.summary)
    print("[corruption] === DONE ===", flush=True)
