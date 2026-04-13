WITH _programs AS
(
  FROM base_programs
)
,_offers AS
(
  FROM offers
  WHERE program_key IN
  (
    SELECT
       program_key
    FROM _programs
  )
)
FROM _offers
;
