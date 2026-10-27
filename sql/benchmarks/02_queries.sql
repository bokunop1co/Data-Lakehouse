-- Same logical query against both tables; {table} is replaced by benchmark.py.
-- name: one_month_one_currency
SELECT rate_date, ars_rate
FROM `{project}.{dataset}.{table}`
WHERE rate_date BETWEEN '2025-06-01' AND '2025-06-30'
  AND currency_code = 'C042';

-- name: one_year_all_currencies
SELECT currency_code, AVG(ars_rate) AS avg_rate
FROM `{project}.{dataset}.{table}`
WHERE rate_date BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY currency_code;
