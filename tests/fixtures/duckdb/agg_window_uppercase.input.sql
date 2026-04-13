SELECT
  count(*) AS total,
  sum(amount) AS total_amount,
  avg(price) AS avg_price,
  row_number() OVER (PARTITION BY user_id ORDER BY created_at) AS rn,
  rank() OVER (ORDER BY amount DESC) AS rnk,
  lag(amount, 1) OVER (ORDER BY created_at) AS prev_amount,
  regexp_extract(description, '[A-Z]{3}-\d+', 0) AS code,
  strftime(created_at, '%Y-%m') AS month,
  date_trunc('week', created_at) AS week_start
FROM orders
