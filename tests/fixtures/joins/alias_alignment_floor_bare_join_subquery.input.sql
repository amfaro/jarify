-- jarify: set min-column-alias = 34
SELECT a AS c, b AS d FROM t JOIN (SELECT id AS i, v AS w FROM u) s ON s.i = t.id;

-- jarify: set alias-visual-guide-interval = 12
SELECT strptime(hired_on, '%Y%m%d')::date AS hired_on, b AS d FROM t JOIN (SELECT id AS i, v AS w FROM u) s ON s.i = t.id;
