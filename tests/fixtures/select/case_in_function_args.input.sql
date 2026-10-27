-- A searched CASE as a later argument of a wrapped if()
SELECT
  if(p.entry_type_id = 3, CASE WHEN regexp_full_match(p.description, '^B2S.*$') THEN 'b2s_order' WHEN regexp_full_match(p.description, '^.*special.*$') THEN 'special_order' ELSE 'unknown' END, 'nomination') AS kind
FROM p
;

-- A CASE makes an if() that would fit on one line wrap
SELECT
  if(x, CASE WHEN a THEN 1 WHEN b THEN 2 ELSE 3 END, 0) AS k
FROM t
;

-- A searched and a simple CASE as the first argument of if()
SELECT
  if(CASE WHEN a > 0 THEN b WHEN a < 0 THEN c ELSE false END, 'x', 'y') AS searched_first
  , if(CASE k WHEN 1 THEN true WHEN 2 THEN false END, 'x', 'y') AS simple_first
FROM t
;

-- A simple CASE as a later argument of if()
SELECT
  if(x, 'none', CASE p.kind WHEN 1 THEN 'one' WHEN 2 THEN 'two' ELSE 'other' END) AS simple_later
FROM p
;

-- A searched and a simple CASE as the first and as a later argument of format()
SELECT
  format(CASE WHEN a THEN '{} a' WHEN b THEN '{} b' END, x) AS searched_first
  , format('{} {}', x, CASE WHEN a THEN 1 WHEN b THEN 2 ELSE 3 END) AS searched_later
  , format(CASE p.kind WHEN 1 THEN '{} one' ELSE '{} other' END, x) AS simple_first
  , format('{} {}', x, CASE p.kind WHEN 1 THEN 'one' WHEN 2 THEN 'two' ELSE 'other' END) AS simple_later
FROM p
;

-- A CASE as the only argument, inside a call nested in if(), and before an operator
SELECT
  SUM(CASE WHEN a THEN 1 WHEN b THEN 2 END) AS only_arg
  , if(x, ifnull(CASE WHEN a THEN 1 WHEN b THEN 2 END, 0), 1) AS nested_call
  , if(x, CASE WHEN a THEN 1 WHEN b THEN 2 END + 1, 0) AS before_operator
FROM t
;
