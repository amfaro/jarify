-- Comments on WHEN, THEN and ELSE go on their own line above the keyword
SELECT
  CASE
    -- first branch
    WHEN a = 1 THEN /* nested */ CASE WHEN b = 1 THEN 1 WHEN b = 2 THEN 2 END
    WHEN -- second branch
      a = 2
    -- above then
    THEN 3
    -- fallback
    ELSE /* none */ 4
  END AS v
FROM t
;

-- A simple CASE puts them above the WHEN line
SELECT
  CASE x
    -- one
    WHEN 1 THEN /* first */ 'a'
    WHEN 2 THEN 'b'
    ELSE -- other
      'c'
  END AS v
FROM t
;

-- A nested CASE puts them above its own keywords
SELECT
  CASE
    WHEN a = 1 THEN CASE WHEN b = 1 THEN /* inner */ 1 WHEN b = 2 THEN 2 END
    WHEN a = 2 THEN 3
  END AS v
FROM t
;

-- A single-WHEN CASE with a keyword comment stays CASE instead of becoming IF()
SELECT CASE WHEN a = 1 THEN /* only one */ 1 END AS v FROM t
;
