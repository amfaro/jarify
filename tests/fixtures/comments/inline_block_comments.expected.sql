-- A comment that can't end its line becomes a block comment
SELECT
   a /* note */ + 1             AS c
  ,a + 1 /* after the sum */    AS d
  ,a /* before the cast */::int AS e
  ,longer_column_name           AS f
FROM t
ORDER BY
   a /* before the direction */ DESC
;

SELECT
   a
FROM t
WHERE a BETWEEN 1 /* low */ AND 2
;
