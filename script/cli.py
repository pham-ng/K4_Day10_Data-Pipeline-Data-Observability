from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src/ to sys.path
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.config import load_settings
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question
from pipelines.phase1 import main as run_phase1
from pipelines.corruption_flow import main as run_corruption_flow


def main():
    parser = argparse.ArgumentParser(
        description="Day 10: Data Pipeline & Data Observability CLI Runner"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Chạy toàn bộ pipeline End-to-End (Phase 1 Baseline + Phase 2 Corruption & Repair)",
    )
    parser.add_argument(
        "--phase1",
        action="store_true",
        help="Chạy Pha 1: Baseline Ingestion, ChromaDB Indexing, Evaluation & Quality Report",
    )
    parser.add_argument(
        "--phase2",
        action="store_true",
        help="Chạy Pha 2: Data Corruption, Re-eval, Data Repair từ Raw Snapshot & Comparison Report",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Đặt câu hỏi trực tiếp cho RAG Agent (ví dụ: --query 'What is force control?')",
    )

    args = parser.parse_args()

    if args.all or (not args.phase1 and not args.phase2 and not args.query):
        print("=== CHẠY TOÀN BỘ DATA PIPELINE END-TO-END (PHASE 1 + PHASE 2) ===")
        print("\n--- PHASE 1: BASELINE PIPELINE ---")
        run_phase1()
        print("\n--- PHASE 2: CORRUPTION & REPAIR FLOW ---")
        run_corruption_flow()
        print("\n🎉 HOÀN THÀNH TOÀN BỘ PIPELINE END-TO-END TRÔI CHẢY!")

    elif args.phase1:
        print("=== CHẠY PHASE 1: BASELINE PIPELINE ===")
        run_phase1()

    elif args.phase2:
        print("=== CHẠY PHASE 2: CORRUPTION & REPAIR FLOW ===")
        run_corruption_flow()

    if args.query:
        print(f"\n=== DEMO RAG QA AGENT ===")
        settings = load_settings()
        print(f"[CLI] Querying ChromaDB Vector Index for: '{args.query}' ...")
        index = LocalEmbeddingIndex.load(settings)
        response = answer_question(args.query, index=index, settings=settings)
        print(f"\n[Q]: {response.question}")
        print(f"[A]: {response.answer}")
        print(f"[Retrieved Contexts]: {len(response.retrieved_contexts)} documents retrieved.")


if __name__ == "__main__":
    main()
