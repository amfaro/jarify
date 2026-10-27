-- A nested join written without parentheses
SELECT
   t.a
  ,v.b
FROM t
INNER JOIN (
  u
  INNER JOIN v ON v.id = u.id
) ON u.id = t.id
;

SELECT
   tt.a
FROM tbl tt
LEFT JOIN (
  users             uu
  INNER JOIN visits vv ON vv.uid = uu.id
) ON uu.id = tt.uid
LEFT JOIN other_things o ON o.id = tt.oid
;

SELECT
   t.a
FROM t
INNER JOIN (
  u
  INNER JOIN v USING (id)
) USING (id)
;

-- Already parenthesized
SELECT
   tt.a
FROM tbl tt
LEFT JOIN (
  users                uu
  INNER JOIN visits    vv ON vv.uid = uu.id
  LEFT JOIN x.yy_things y ON y.vid = vv.id
) ON uu.id = tt.uid
;

FROM t
INNER JOIN (
  u
  INNER JOIN (
    v
    INNER JOIN w ON w.id = v.id
  ) ON v.id = u.id
) ON u.id = t.id
;
