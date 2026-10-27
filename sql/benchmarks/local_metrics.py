"""Local stand-in for the GCP run: replays silver/gold in DuckDB over the ingested Parquet.

Usage (after `make ingest-dry START=... END=...`):
  python sql/benchmarks/local_metrics.py

Silver, gold and the assertions mirror the Dataform definitions. Benchmark bytes are modeled with
BigQuery's documented logical sizes (DATE/FLOAT64 = 8 B, STRING = 2 B + length) and partition
pruning on rate_date. They are estimates, not BigQuery job statistics; clustering is not reflected.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

DATA_GLOB = (Path(__file__).resolve().parents[2] / "data" / "**" / "*.parquet").as_posix()

con = duckdb.connect()


# Returns the first row of a query.
def q(sql: str) -> tuple:
    return con.sql(sql).fetchone()


con.sql(f"CREATE VIEW bronze AS SELECT * FROM read_parquet('{DATA_GLOB}', hive_partitioning=true)")

# Same logic as dataform/definitions/silver/stg_bcra_fx.sqlx (full refresh).
con.sql("""
CREATE TABLE silver AS
WITH src AS (
  SELECT dt AS rate_date, UPPER(TRIM(currency_code)) AS currency_code,
         TRIM(currency_name) AS currency_name,
         CAST(tipo_pase AS DECIMAL(38,9)) AS usd_parity,
         CAST(tipo_cotizacion AS DECIMAL(38,9)) AS ars_rate, ingested_at
  FROM bronze)
SELECT * EXCLUDE (ingested_at) FROM src
QUALIFY ROW_NUMBER() OVER (PARTITION BY rate_date, currency_code ORDER BY ingested_at DESC) = 1
""")

# Same logic as dataform/definitions/gold/fx_daily_variation.sqlx.
con.sql("""
CREATE TABLE gold AS
SELECT rate_date, currency_code, currency_name, ars_rate,
  LAG(ars_rate) OVER w AS prev_ars_rate,
  ars_rate - LAG(ars_rate) OVER w AS abs_change,
  CASE WHEN LAG(ars_rate) OVER w = 0 THEN NULL
       ELSE (ars_rate - LAG(ars_rate) OVER w) / LAG(ars_rate) OVER w END * 100 AS pct_change
FROM silver
WINDOW w AS (PARTITION BY currency_code ORDER BY rate_date)
""")

print("bronze rows:", q("SELECT count(*) FROM bronze")[0])
print("days with data:", q("SELECT count(DISTINCT dt) FROM bronze")[0])
print("date range:", q("SELECT min(dt)::VARCHAR, max(dt)::VARCHAR FROM bronze"))
print("silver rows:", q("SELECT count(*) FROM silver")[0])
print("gold rows:", q("SELECT count(*) FROM gold")[0])
print("distinct currencies:", q("SELECT count(DISTINCT currency_code) FROM silver")[0])

# Same checks Dataform generates from the sqlx assertions config.
checks = {
    "silver nonNull": "SELECT count(*) FROM silver WHERE rate_date IS NULL OR currency_code IS NULL OR ars_rate IS NULL",
    "silver uniqueKey": "SELECT count(*) FROM (SELECT rate_date, currency_code FROM silver GROUP BY ALL HAVING count(*) > 1)",
    "silver rowConditions": "SELECT count(*) FROM silver WHERE NOT (ars_rate >= 0 AND usd_parity >= 0)",
    "gold nonNull": "SELECT count(*) FROM gold WHERE rate_date IS NULL OR currency_code IS NULL OR ars_rate IS NULL",
    "gold uniqueKey": "SELECT count(*) FROM (SELECT rate_date, currency_code FROM gold GROUP BY ALL HAVING count(*) > 1)",
    "no_extreme_daily_moves": "SELECT count(*) FROM gold WHERE ABS(pct_change) > 50",
}
for name, sql in checks.items():
    bad = q(sql)[0]
    print(f"assert {name}: {'PASS' if bad == 0 else 'FAIL'} ({bad} bad rows)")
if q(checks["no_extreme_daily_moves"])[0]:
    print(
        con.sql(
            "SELECT rate_date::VARCHAR, currency_code, pct_change FROM gold "
            "WHERE ABS(pct_change) > 50 ORDER BY 1 LIMIT 10"
        ).fetchall()
    )

# Synthetic dataset, same shape as 01_setup.sql (padding is never referenced, so it is not scanned).
con.sql("""
CREATE TABLE flat AS
SELECT d::DATE AS rate_date, 'C' || LPAD(CAST(c AS VARCHAR), 3, '0') AS currency_code,
       ROUND(100 + 900 * random(), 4) AS ars_rate
FROM generate_series(DATE '2015-01-01', DATE '2025-12-31', INTERVAL 1 DAY) t(d), range(1, 151) u(c)
""")
print("synthetic rows:", q("SELECT count(*) FROM flat")[0])

ROW_BYTES = "8 + (2 + strlen(currency_code)) + 8"  # rate_date + currency_code + ars_rate
CASES = {
    "one_month_one_currency": "rate_date BETWEEN '2025-06-01' AND '2025-06-30'",
    "one_year_all_currencies": "rate_date BETWEEN '2025-01-01' AND '2025-12-31'",
}
for name, predicate in CASES.items():
    flat = q(f"SELECT sum({ROW_BYTES}) FROM flat")[0]  # no partitioning: full scan
    opt = q(f"SELECT sum({ROW_BYTES}) FROM flat WHERE {predicate}")[0]  # partition pruning only
    print(f"{name}: flat={flat} opt={opt} saved={1 - opt / flat:.1%}")
