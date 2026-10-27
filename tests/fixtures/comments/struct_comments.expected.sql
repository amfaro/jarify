-- Comments in a struct literal stay with their entries, which go one per line
SELECT
   {
     'a': 1 -- first
    ,'b': 2
  }         AS s1
  ,{
     'a': 1 -- opening
    ,'b': 2
  }         AS s2
  ,{
     'a': 1 -- value
  }         AS s3
  ,{
     'a' /* key */: 1
  }         AS s4
  ,{'a': 1} AS s5 -- after the struct
FROM t
;

-- Commented-out entries on their own lines
SELECT
   list(
     {
        'attribute': attribute
       ,'seq': seq
       -- ,'provided_value': provided_value
       ,'value': mapped_value
     }
     ORDER BY seq
  ) AS custom_field_values
FROM t
GROUP BY ALL
;
