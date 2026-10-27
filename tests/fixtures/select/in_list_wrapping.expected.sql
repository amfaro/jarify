-- A short IN list stays inline
SELECT
   a
FROM t
WHERE c IN ('NLD', 'DEU', 'POL')
;

-- A long IN list puts one value per line
SELECT
   a
FROM t
WHERE c IN (
   'NLD'
  ,'DEU'
  ,'POL'
  ,'ISR'
  ,'FRA'
  ,'GBR'
  ,'ITA'
  ,'ESP'
  ,'AUT'
  ,'BEL'
  ,'SWE'
  ,'CHE'
  ,'ROU'
  ,'CZE'
  ,'DNK'
  ,'PRT'
  ,'FIN'
  ,'HUN'
  ,'GRC'
  ,'UKR'
  ,'IRL'
  ,'NOR'
)
;

-- A long NOT IN list inside a multi-condition WHERE
SELECT
   a
FROM t
WHERE client_id = 1
  AND NOT country_code IN (
     'NLD'
    ,'DEU'
    ,'POL'
    ,'ISR'
    ,'FRA'
    ,'GBR'
    ,'ITA'
    ,'ESP'
    ,'AUT'
    ,'BEL'
    ,'SWE'
    ,'CHE'
    ,'ROU'
    ,'CZE'
    ,'DNK'
    ,'PRT'
    ,'FIN'
    ,'HUN'
    ,'GRC'
    ,'UKR'
    ,'IRL'
    ,'NOR'
  )
  AND active
;

-- The values fit on one line, but the whole `col IN (…)` doesn't
SELECT
   a
FROM t
WHERE a_really_quite_long_column_name_that_pushes_the_line_past_the_limit IN (
   'value_one'
  ,'value_two'
  ,'value_three'
  ,'value_four'
  ,'value_five'
)
;

-- In a SELECT list, the alias follows the closing paren
WITH _recs AS
(
  SELECT
     rec_id
    ,rec_status_key IN (
       'nom_status_approved'
      ,'nom_status_awarded'
      ,'nom_status_terminated'
      ,'nom_status_pending_redemption'
    ) AS successful
  FROM recs
)
FROM _recs
;
