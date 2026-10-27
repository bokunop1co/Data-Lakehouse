"""CLI: python -m bcra_ingest.cli --start 2025-01-01 --end 2025-01-31 --bucket my-bucket"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .client import BcraClient
from .storage import upload_to_gcs, write_partitioned
from .transform import flatten_day

LOG = logging.getLogger("bcra_ingest")


# Genera cada fecha entre el inicio y el fin, ambos inclusive.
def daterange(start: date, end: date) -> Iterator[date]:
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


# Define y parsea los argumentos de línea de comandos.
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest BCRA exchange rates into the GCS bronze layer.")
    p.add_argument("--start", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    p.add_argument("--end", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    p.add_argument("--bucket", help="Bronze GCS bucket name (required unless --dry-run)")
    p.add_argument("--out-dir", type=Path, default=Path("./data"), help="Local Parquet root")
    p.add_argument("--dry-run", action="store_true", help="Write local Parquet only, no upload")
    p.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Disable TLS verification (BCRA cert chain workaround; unsafe)",
    )
    args = p.parse_args(argv)
    if args.end < args.start:
        p.error("--end must be >= --start")
    if not args.dry_run and not args.bucket:
        p.error("--bucket is required unless --dry-run is set")
    return args


# Punto de entrada: descarga, transforma, guarda y opcionalmente sube los datos.
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    client = BcraClient(verify_tls=not args.insecure_skip_tls_verify)

    frames = []
    for day in daterange(args.start, args.end):
        df = flatten_day(client.get_day(day))
        LOG.info("%s: %d rows", day, len(df))
        if not df.empty:
            frames.append(df)

    if not frames:
        LOG.warning("No data in range (weekends/holidays only?)")
        return 0

    files = write_partitioned(pd.concat(frames, ignore_index=True), args.out_dir)
    LOG.info("wrote %d partition files under %s", len(files), args.out_dir)

    if args.dry_run:
        LOG.info("dry-run: skipping GCS upload")
    else:
        upload_to_gcs(files, args.out_dir, args.bucket)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
