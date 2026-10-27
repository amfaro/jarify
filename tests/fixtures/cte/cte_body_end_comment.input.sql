WITH _tf AS
(
  FROM time_frames
  WHERE time_frame_key IN ('current_month', 'trailing_12_months') -- only time_frames where ends_on >= today
  -- because we only keep track of last_visit_at
)
,_columns_only AS
(
  SELECT
     1 AS a
    ,2 AS b
  -- c comes later
)
,_last AS
(
  SELECT a, b FROM _columns_only
  -- the last CTE before the main SELECT
)
SELECT a, b FROM _last
;

WITH _after_as AS -- a comment after AS
(
  SELECT 1 AS x
  -- end of _after_as
)
,_block AS
(
  SELECT x FROM _after_as
  /* commented out:
  WHERE x > 0 */
)
SELECT x FROM _block
;
