-- Comments in a struct literal stay with their entries, which go one per line
SELECT
  {'a': 1, -- first
   'b': 2} AS s1,
  { -- opening
   'a': 1, 'b': 2} AS s2,
  {'a': /* value */ 1} AS s3,
  {'a' /* key */: 1} AS s4,
  {'a': 1} -- after the struct
    AS s5
FROM t
;

-- Commented-out entries on their own lines
SELECT
  list({
    'attribute': attribute
   ,'seq': seq
-- ,'provided_value': provided_value
   ,'value': mapped_value
  } ORDER BY seq) AS custom_field_values
FROM t
GROUP BY ALL
;
