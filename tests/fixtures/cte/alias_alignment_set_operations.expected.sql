-- The CTEs and every branch of the final UNION share one AS column
WITH _owners AS
(
  SELECT
     ou.organization_id
    ,ou.user_id                      AS owner_user_id
  FROM organization_users ou
)
SELECT
   cp.organization_id
  ,'margin'                          AS category
  ,SUM(cp.margin * cp.current_units) AS value
FROM customer_products cp
INNER JOIN _owners      o ON o.organization_id = cp.organization_id
GROUP BY ALL
UNION ALL
SELECT
   rh.organization_id
  ,'rebate'                          AS category
  ,SUM(rh.rebate)                    AS value
FROM rebate_history rh
GROUP BY ALL
;

-- A CTE whose body is a UNION shares it too
WITH _all AS
(
  SELECT
     id       AS user_id
  FROM managers
  UNION ALL
  SELECT
     admin_id AS user_id
  FROM program_admins
)
SELECT
   user_id
  ,COUNT(*)   AS row_count
FROM _all
GROUP BY ALL
;

-- Fewer than two aliases between the branches: nothing to align
SELECT
   user_id
FROM managers
UNION
SELECT
   admin_id AS user_id
FROM program_admins
;
