WITH _base AS
(
  SELECT
     1
)
-- filter by parameters
,_programs AS
(
  SELECT
     qualification_type
  FROM _base
)
-- two line comment
-- explaining the next cte
,_summary AS
(
  SELECT
     COUNT()
  FROM _programs
)
FROM _summary
;
