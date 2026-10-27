"""Compare bytes processed on a flat vs partitioned+clustered table using dry runs.

Dry runs are free: BigQuery only estimates bytes, nothing is executed.

Usage:
  python benchmark.py --project my-proj --dataset gold --setup   # creates the tables (small real cost)
  python benchmark.py --project my-proj --dataset gold           # dry-run comparison only

Caveat: dry-run estimates for clustered tables are upper bounds; the actual bytes
billed can be lower after clustering pruning. For exact numbers, run the queries and
read total_bytes_billed from INFORMATION_SCHEMA.JOBS (see README).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from google.cloud import bigquery

HERE = Path(__file__).parent


# Carga las consultas SQL del benchmark desde disco.
def load_queries() -> dict[str, str]:
    text = (HERE / "02_queries.sql").read_text()
    parts = re.split(r"^-- name: (\w+)\n", text, flags=re.MULTILINE)
    # parts = [preamble, name1, sql1, name2, sql2, ...]
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


# Devuelve los bytes que procesaría una consulta mediante un dry run.
def dry_run_bytes(client: bigquery.Client, sql: str) -> int:
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    return client.query(sql, job_config=cfg).total_bytes_processed


# Ejecuta el benchmark y muestra la comparación de bytes procesados.
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--dataset", default="gold")
    p.add_argument("--location", default="southamerica-east1")
    p.add_argument("--setup", action="store_true", help="Create the benchmark tables first")
    args = p.parse_args()

    client = bigquery.Client(project=args.project, location=args.location)

    if args.setup:
        setup = (HERE / "01_setup.sql").read_text()
        client.query(setup.format(project=args.project, dataset=args.dataset)).result()
        print("Benchmark tables created.")

    print(f"{'query':28} {'flat (MB)':>12} {'optimized (MB)':>16} {'saved':>8}")
    for name, sql in load_queries().items():
        sizes = {}
        for label, table in (("flat", "bench_fx_flat"), ("opt", "bench_fx_opt")):
            q = sql.format(project=args.project, dataset=args.dataset, table=table)
            sizes[label] = dry_run_bytes(client, q)
        saved = 1 - sizes["opt"] / sizes["flat"] if sizes["flat"] else 0
        print(f"{name:28} {sizes['flat'] / 1e6:12.2f} {sizes['opt'] / 1e6:16.2f} {saved:8.1%}")


if __name__ == "__main__":
    main()
