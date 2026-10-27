-- Creates two copies of the same synthetic FX dataset (~4,000 days x 150 currencies = ~600k rows):
--   bench_fx_flat : no partitioning, no clustering
--   bench_fx_opt  : PARTITION BY rate_date, CLUSTER BY currency_code
-- Synthetic data is used because real BCRA data is too small to show a meaningful difference.
-- Placeholders {project} and {dataset} are filled in by benchmark.py.

CREATE OR REPLACE TABLE `{project}.{dataset}.bench_fx_flat` AS
SELECT
  d AS rate_date,
  CONCAT('C', LPAD(CAST(c AS STRING), 3, '0')) AS currency_code,
  ROUND(100 + 900 * RAND(), 4) AS ars_rate,
  REPEAT('x', 100) AS padding  -- gives rows realistic width
FROM UNNEST(GENERATE_DATE_ARRAY('2015-01-01', '2025-12-31')) AS d,
     UNNEST(GENERATE_ARRAY(1, 150)) AS c;

CREATE OR REPLACE TABLE `{project}.{dataset}.bench_fx_opt`
PARTITION BY rate_date
CLUSTER BY currency_code AS
SELECT * FROM `{project}.{dataset}.bench_fx_flat`;
