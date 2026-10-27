-- A GROUP BY with a comment keeps its list, even when the SELECT list has the same comment
SELECT
   n.nominee_user_id
  ,n.nomination_application_id -- ,np.released_at
  ,SUM(point_value) AS point_value
FROM nominations n
GROUP BY
   n.nominee_user_id
  ,n.nomination_application_id -- ,np.released_at
;

-- A comment on GROUP BY itself goes above GROUP BY ALL
SELECT
   a
  ,SUM(b) AS s
FROM t
-- by a
GROUP BY ALL
;
