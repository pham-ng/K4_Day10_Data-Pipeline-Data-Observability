from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, write_csv, write_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records


def main() -> None:
    settings = load_settings()

    # Step 3: load raw records tu file cu, hoac fetch moi neu chua co / REFRESH_SOURCE=1
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        print(f"[step3] Fetching from {settings.source_api} ...")
        records = fetch_source_records(settings)
    else:
        print(f"[step3] Loading cached raw records from {settings.paths.raw_records_json}")
        records = load_raw_records(settings.paths.raw_records_json)

    print(f"[step3] Raw records: {len(records)}")

    # Step 4: clean data
    df = build_clean_dataframe(records, run_date=now_utc())
    print(f"[step4] Clean records: {len(df)}")

    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    print(f"[step4] Saved -> {settings.paths.clean_csv}")
    print(f"[step4] Saved -> {settings.paths.clean_json}")

    if not df.empty:
        print(df[["paper_id", "title", "published", "age_days"]].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
