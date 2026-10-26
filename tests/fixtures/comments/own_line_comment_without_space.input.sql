WITH _a AS
(
  SELECT
     x
    --,y
    --,z
    ,w
  FROM t
)
--second CTE
,_b AS
(
  SELECT
     v
  FROM u
)
SELECT
   x
  ,v
FROM _a
CROSS JOIN _b
;
