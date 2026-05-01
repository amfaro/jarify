WITH outer_group AS (
  WITH seed_group AS (
    SELECT alpha_value AS seed_one, beta_metric AS seed_two FROM source_a
  )
  SELECT seed_one AS outer_one, seed_two AS outer_two FROM seed_group
),
sibling_group AS (
  SELECT gamma_code AS sibling_one, delta_indicator AS sibling_two FROM source_b
)
SELECT outer_one AS final_one, sibling_two AS final_two
FROM outer_group
JOIN sibling_group ON outer_one = sibling_one
