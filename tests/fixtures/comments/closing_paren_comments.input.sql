-- A comment before a subquery's closing paren stays at the end of its body
SELECT s.a
FROM (
  SELECT a FROM t
  -- end of body
) s
LEFT JOIN (
  SELECT a FROM u
  /* end of the joined body */
) w ON w.a = s.a
;

SELECT s.a
FROM (SELECT a FROM t) -- after the paren
  s
;

-- Comments on if() are kept, as on any other call
SELECT
  -- above the call
  if(b = 1, 'x', 'y') AS w
 ,if(a = 1, 'x', 'y') -- between the call and AS
    AS v
 ,count(*) FILTER (WHERE a = 1) /* filtered */ AS n
FROM t
;
