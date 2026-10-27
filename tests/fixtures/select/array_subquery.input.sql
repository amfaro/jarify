-- ARRAY(query) is laid out like a scalar subquery
SELECT array(SELECT a FROM some_table_name WHERE some_condition_column = 1 AND another_condition_column = 2) AS v, b AS w FROM t;

SELECT array(WITH x AS (SELECT 1 AS a) SELECT a FROM x) AS v FROM t;

SELECT array(SELECT 1 UNION ALL SELECT 2) AS v;

SELECT a FROM t WHERE list_contains(array(SELECT a FROM u), 1);

-- A list literal and a short ARRAY(query) in a one-line call keep their one-line form
SELECT [1, 2] AS l, if(x, array(SELECT a FROM u), []) AS v FROM t;
