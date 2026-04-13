SELECT
   COUNT(*)                                                     AS total
  ,SUM(amount)                                                  AS total_amount
  ,AVG(price)                                                   AS avg_price
  ,ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at) AS rn
  ,RANK() OVER (ORDER BY amount DESC)                           AS rnk
  ,LAG(amount, 1) OVER (ORDER BY created_at)                    AS prev_amount
  ,regexp_extract(description, '[A-Z]{3}-\d+')                  AS code
  ,strftime(created_at, '%Y-%m')                                AS month
  ,date_trunc('WEEK', created_at)                               AS week_start
FROM orders
;
