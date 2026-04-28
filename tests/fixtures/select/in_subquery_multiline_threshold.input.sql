SELECT *
FROM offers
WHERE program_key IN
(
  SELECT
     program_key
  FROM _programs
  WHERE some_very_long_column_name_here = 'a_value_that_makes_this_exceed_the_line_length_threshold'
)
;
