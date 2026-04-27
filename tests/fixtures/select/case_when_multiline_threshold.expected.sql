-- 3 WHEN branches: always multi-line
SELECT
   *
  ,CASE o.part
    WHEN 'AND' THEN '&&'
    WHEN 'OR'  THEN '||'
    WHEN 'NOT' THEN '!'
    ELSE ifnull(qr.met::text, o.part)
  END AS expr
FROM data
;

-- 2 WHEN branches: also multi-line (all CASE always multi-line in pretty mode)
SELECT
   CASE status
    WHEN 'active'   THEN true
    WHEN 'inactive' THEN false
  END AS is_active
FROM t
;
