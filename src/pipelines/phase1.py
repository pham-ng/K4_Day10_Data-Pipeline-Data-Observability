from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question

DEMO_SAMPLE_SIZE = 3


def main() -> None:
    """Xay dung baseline pipeline end-to-end.

    1. Load settings.
    2. Load hoac fetch raw records.
    3. Clean data.
    4. Save clean CSV/JSON.
    5. Build Chroma index.
    6. Tao hoac load evaluation set.
    7. Evaluate.
    8. Run quality checks va freshness report.
    9. Tao markdown report.
    10. Demo agent tren vai sample question.
    """
    print("[phase1] === START ===", flush=True)
    print("[phase1] step 1/10: loading settings ...", flush=True)
    settings = load_settings()
    print(f"[phase1] settings loaded: provider={settings.llm_provider} model={settings.model_name}", flush=True)

    # 2. Load hoac fetch raw records.
    print("[phase1] step 2/10: raw records ...", flush=True)
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        print(f"[phase1]   fetching raw records from {settings.source_api} ...", flush=True)
        records = fetch_source_records(settings)
    else:
        print(f"[phase1]   loading cached raw records from {settings.paths.raw_records_json}", flush=True)
        records = load_raw_records(settings.paths.raw_records_json)
    print(f"[phase1]   raw records: {len(records)}", flush=True)

    # 3-4. Clean data + save clean CSV/JSON.
    print("[phase1] step 3-4/10: cleaning data ...", flush=True)
    df = build_clean_dataframe(records, run_date=now_utc())
    if df.empty:
        raise RuntimeError("Cleaning produced an empty dataframe; check the raw source data.")
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))
    print(f"[phase1]   clean records: {len(df)} -> {settings.paths.clean_csv}", flush=True)

    # 5. Build Chroma index.
    print(
        "[phase1] step 5/10: building embedding index "
        "(first run tai model sentence-transformers ve, co the mat vai phut) ...",
        flush=True,
    )
    index = LocalEmbeddingIndex.build(df, settings=settings, embeddings_output_path=settings.paths.embeddings_json)
    print(f"[phase1]   index built: collection={index.collection_name}, documents={len(index.documents)}", flush=True)

    # 6. Tao hoac load evaluation set.
    print("[phase1] step 6/10: evaluation set ...", flush=True)
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(df, settings.paths.eval_testset)
        print(f"[phase1]   built new test set: {len(test_set)} questions", flush=True)
    else:
        test_set = read_json(settings.paths.eval_testset)
        print(f"[phase1]   loaded cached test set: {len(test_set)} questions", flush=True)

    # 7. Evaluate.
    print(f"[phase1] step 7/10: evaluating {len(test_set)} questions (goi LLM judge, co the cham) ...", flush=True)
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print(
        f"[phase1]   retrieval_hit_rate={bundle.summary['retrieval_hit_rate']:.3f} "
        f"mean_token_f1={bundle.summary['mean_token_f1']:.3f} "
        f"judge_accuracy={bundle.summary['judge_accuracy']:.3f}",
        flush=True,
    )

    # 8. Run quality checks va freshness report.
    print("[phase1] step 8/10: data quality + freshness checks ...", flush=True)
    quality = run_data_quality_checks(df, settings=settings, report_name="baseline")
    freshness = build_freshness_report(df, settings=settings, report_path=settings.paths.freshness_report)
    print(f"[phase1]   quality_success={quality.get('success')} is_fresh={freshness.get('is_fresh')}", flush=True)

    # 9. Tao markdown report.
    print("[phase1] step 9/10: writing markdown report ...", flush=True)
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_records": len(records),
        "clean_records": len(df),
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )
    print(f"[phase1]   report -> {settings.paths.baseline_report}", flush=True)

    # 10. Demo agent tren vai sample question (dung qa.answer_question, khong can LLM).
    print(f"[phase1] step 10/10: demo qa on {DEMO_SAMPLE_SIZE} sample questions ...", flush=True)
    demo_answers = []
    for item in test_set[:DEMO_SAMPLE_SIZE]:
        result = answer_question(item["question"], settings=settings, index=index)
        print(f"[phase1]   Q: {item['question']}", flush=True)
        print(f"[phase1]   A: {result.answer}", flush=True)
        demo_answers.append(
            {
                "question": item["question"],
                "answer": result.answer,
                "retrieved_doc_ids": result.retrieved_doc_ids,
                "retrieved_titles": result.retrieved_titles,
            }
        )
    write_json(settings.paths.demo_answers, demo_answers)
    print(f"[phase1]   demo answers -> {settings.paths.demo_answers}", flush=True)
    print("[phase1] === DONE ===", flush=True)
