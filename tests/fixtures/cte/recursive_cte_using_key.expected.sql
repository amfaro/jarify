WITH RECURSIVE _hierarchy USING KEY (position_id) AS
(
  SELECT
     position_id
    ,parent_position_id
    ,0 AS depth
  FROM positions
  WHERE parent_position_id IS NULL
  UNION
  SELECT
     p.position_id
    ,p.parent_position_id
    ,h.depth + 1 AS depth
  FROM positions        p
  INNER JOIN _hierarchy h ON p.parent_position_id = h.position_id
)
,_pairs (a, b) USING KEY (a, b) AS MATERIALIZED
(
  SELECT
     1
    ,2
)
SELECT
   *
FROM _hierarchy
CROSS JOIN _pairs
;
