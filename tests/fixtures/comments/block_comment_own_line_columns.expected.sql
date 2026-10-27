SELECT
   a
  ,b
  /* ,c
  ,d */
  ,e
  -- one line between
  ,f
FROM t
;

SELECT
   -- one line before the first column
   a
  ,b
FROM t
;

SELECT
   /* several lines
     before the first column */
   a
  ,b
FROM t
;

SELECT
   a
  ,b
-- one line after the last column
FROM t
;

SELECT
   a
  ,b
/* ,c
  ,d */
FROM t
;

WITH _x AS
(
  SELECT
     a
    /* ,b
    ,c */
    ,d
  FROM t
)
FROM _x
;
