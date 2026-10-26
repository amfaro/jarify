-- Commented ON conditions break like WHERE, aligned after ON
SELECT x.a, y.b
FROM some_table x
LEFT JOIN other_table y ON x.id = y.id -- match
  OR x.alt_id = y.id -- fallback
JOIN third z ON z.id = x.id
  -- own line
  AND z.k IS NOT NULL
;

-- A single commented ON condition stays inline
SELECT a.x, b.y FROM a
LEFT JOIN b ON a.id = b.id -- only
;
