-- With trailing commas, a comment above a column stays above it
SELECT
  -- above the first column
  a + 1 AS v,
  b, -- after b
  -- above the CASE
  CASE WHEN x THEN 1 WHEN y THEN 2 END AS w, -- after the CASE
  ifnull(a, 1)
  -- written before a leading comma
  , z
FROM t
WHERE c IN (
  -- above the first value
  1,
  -- above the second value
  2
)
GROUP BY
  -- above the first key
  a,
  b
ORDER BY
  ROW_NUMBER() OVER (
    ORDER BY
      time_frame_key,
      -- above a window key
      client_name
  )
;
