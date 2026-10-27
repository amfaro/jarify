-- A nested join written without parentheses
SELECT t.a, v.b FROM t JOIN u JOIN v ON v.id = u.id ON u.id = t.id;

SELECT tt.a FROM tbl tt LEFT JOIN users uu JOIN visits vv ON vv.uid = uu.id ON uu.id = tt.uid LEFT JOIN other_things o ON o.id = tt.oid;

SELECT t.a FROM t JOIN u JOIN v USING (id) USING (id);

-- Already parenthesized
SELECT tt.a FROM tbl tt LEFT JOIN (users uu JOIN visits vv ON vv.uid = uu.id LEFT JOIN x.yy_things y ON y.vid = vv.id) ON uu.id = tt.uid;

FROM t JOIN u JOIN v JOIN w ON w.id = v.id ON v.id = u.id ON u.id = t.id;

-- A comment on the group's first table
SELECT t.a FROM t LEFT JOIN (
  -- c1
  u JOIN v ON v.id = u.id) ON u.id = t.id;
