-- jarify: set min-column-alias = 34
SELECT a AS c, (SELECT max(x) AS m, min(x) AS n FROM u) AS s FROM t;

-- jarify: set alias-visual-guide-interval = 12
SELECT strptime(hired_on, '%Y%m%d')::date AS hired_on, (SELECT max(x) AS m, min(x) AS n FROM u) AS s FROM t;
