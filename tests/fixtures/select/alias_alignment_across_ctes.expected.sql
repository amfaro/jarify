WITH _a AS
(
  SELECT
     x   AS first
    ,yy  AS second
  FROM t
)
,_b AS
(
  SELECT
     zzz AS third
    ,w   AS fourth
  FROM u
)
SELECT
   q   AS fifth
  ,rr  AS sixth
FROM _a
INNER JOIN _b ON 1 = 1
;
