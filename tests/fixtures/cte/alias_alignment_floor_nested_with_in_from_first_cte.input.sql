-- jarify: set min-column-alias = 34
WITH _a AS (SELECT 1 AS x), _p AS (WITH _c AS (SELECT user_id, strptime(h, '%Y')::date AS hired_on FROM t) FROM _c) SELECT x AS e, x AS f FROM _a;

-- jarify: set alias-visual-guide-interval = 12
WITH _a AS (SELECT 1 AS x), _p AS (WITH _c AS (SELECT user_id, strptime(hired_on, '%Y%m%d')::date AS hired_on FROM t) FROM _c) SELECT x AS e, x AS f FROM _a;
