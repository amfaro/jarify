-- simple searched case: short THEN values, multi-line
SELECT
  CASE status
    WHEN 'active' THEN true
    WHEN 'inactive' THEN false
    ELSE NULL
  END AS is_active
FROM accounts
;

-- simple searched case: OR connectors in THEN stay compact
SELECT
  CASE _operator
    WHEN 'equal_to'                 THEN _actual = _target
    WHEN 'greater_than'             THEN (_target <= 0) OR (_actual > _target)
    WHEN 'greater_than_or_equal_to' THEN (_target <= 0) OR (_actual >= _target)
    WHEN 'less_than'                THEN _actual < _target
    WHEN 'less_than_or_equal_to'    THEN _actual <= _target
  END AS result
FROM t
;

-- general case expression: short THEN values, multi-line
SELECT
  CASE
    WHEN x > 0 THEN 'positive'
    WHEN x < 0 THEN 'negative'
    ELSE 'zero'
  END AS sign
FROM t
;
