-- Comments on VALUES rows stay with their rows
WITH _overrides (country_code, currency_code) AS
(
  VALUES
     ('MDG', 'MGA') -- madagascar
)
SELECT
   country_code
  ,currency_code
FROM _overrides
;

WITH _codes (code, label) AS
(
  VALUES -- the codes
     -- active first
     ('a', 'active')
    ,('i', 'inactive') -- rarely used
    -- the rest
    ,('x', 'other')
)
SELECT
   code
  ,label
FROM _codes
;

INSERT INTO t
VALUES
   (1, 'a')
  -- the second row
  ,(2, 'b') -- last
;
