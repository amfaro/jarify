SELECT
   description ~ '(?i)^b2s.*$'           AS is_b2s
  ,description !~ 'test'                 AS is_real
  ,regexp_full_match(description, 'x.*') AS full_match
  ,regexp_matches(description, 'x')      AS partial_match
FROM points
WHERE description ~ /* entry */ 'Order Entry'
  AND NOT (code ~ '^[0-9]+$')
;
