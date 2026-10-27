-- jarify: set min-column-alias = 34
WITH _a AS
(
  SELECT
     x                             AS a
    ,y                             AS b
  FROM t
)
SELECT
   a                               AS c
  ,b                               AS d
FROM _a
UNION ALL
SELECT
   a
  ,b
FROM _a
;

-- jarify: set alias-visual-guide-interval = 12
WITH _a AS
(
  SELECT
     strptime(hired_on, '%Y%m%d')::date        AS hired_on
    ,y                                         AS b
  FROM t
)
SELECT
   hired_on                        AS c
  ,b                               AS d
FROM _a
UNION ALL
SELECT
   hired_on
  ,b
FROM _a
;
