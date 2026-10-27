-- jarify: set min-column-alias = 34
WITH _a AS
(
  SELECT
     *
     REPLACE (
        0                          AS x
       ,'a'                        AS y
     )
  FROM t
)
SELECT
   x                               AS c
  ,y                               AS d
FROM _a
;

-- jarify: set alias-visual-guide-interval = 12
WITH _a AS
(
  SELECT
     *
     REPLACE (
        strptime(hired_on, '%Y%m%d')::date     AS hired_on
       ,'a'                                    AS y
     )
  FROM t
)
SELECT
   hired_on                        AS c
  ,y                               AS d
FROM _a
;
