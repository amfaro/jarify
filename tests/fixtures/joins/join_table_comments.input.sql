-- A comment after a join's table follows it; /* */ when ON follows
SELECT t.a FROM t INNER JOIN u /* x */ ON u.id = t.id
;

-- A -- comment after the table keeps the ON condition outside it
SELECT t.a FROM t
INNER JOIN u -- matching rows only
ON u.id = t.id
;

-- With an alias, the comment follows the alias, wherever it was written
SELECT x.a, y.b
FROM t x
INNER JOIN u /* before alias */ y ON y.id = x.id
LEFT JOIN v z /* after alias */ ON z.id = x.id
;

-- FROM and aligned blocks
SELECT o.a
FROM orders /* source */ o
LEFT JOIN users /* people */ u ON u.id = o.user_id
LEFT JOIN addresses addr ON addr.id = o.aid
;

-- USING, CROSS JOIN, and a qualified table name
SELECT t.a
FROM t
LEFT JOIN s.u /* by id */ USING (id)
CROSS JOIN w -- every row
;

-- Comments on both the table and its alias stay on the JOIN line
SELECT x.a
FROM t x
LEFT JOIN u /* first */ y /* second */ ON y.id = x.id
;
