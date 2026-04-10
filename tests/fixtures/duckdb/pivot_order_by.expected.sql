WITH _data AS
(
  SELECT
     participant_key
    ,program_key
    ,enrolled
  FROM enrollments
)
PIVOT (
  SELECT
     participant_key
    ,program_key
    ,enrolled
  FROM _data
)
ON participant_key
USING first(enrolled)
ORDER BY
   program_key
  ,participant_key
;
