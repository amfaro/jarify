WITH _base AS (SELECT 1)
,_programs AS -- this is where we filter by parameters
(
  SELECT qualification_type FROM _base
)
SELECT * FROM _programs;
