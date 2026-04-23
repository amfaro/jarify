CREATE OR REPLACE TABLE programs AS
(
  WITH _programs AS
  (
    FROM programs
    {where_clause}
  )
  {with_clause}
  SELECT
     p.*
  FROM _programs p
  {join_clause}
)
;
