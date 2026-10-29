SELECT
   g
  ,BOOL_OR(status IN ('denied')) AS any_denied
  ,BOOL_AND(points > 0)          AS all_positive
  ,BOOL_OR(active)               AS any_active
  ,BOOL_AND(flag::boolean)       AS all_flagged
FROM t
GROUP BY ALL
;

SELECT
   id
  ,BOOL_AND(active) OVER (PARTITION BY g) AS all_active_in_g
FROM t
;
