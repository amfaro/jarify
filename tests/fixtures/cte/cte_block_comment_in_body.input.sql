WITH _managers AS
(
  SELECT
     m.user_id AS root_user_id
    ,u.user_id
    ,u.active  AS user_active
    /* add in for testing
    ,u.manager_id                           AS direct_user_id
    ,CONCAT(u.first_name, ' ', u.last_name) AS user_full_name
    */
  FROM _users m
  INNER JOIN _users u ON u.manager_user_id = m.user_id
)
,_admins AS
(
  SELECT
     pa.user_id AS root_user_id
    /* add in for testing
    ,pa.client_id
    */
    ,u.user_id
  FROM program_admins pa
  INNER JOIN _users u ON u.client_id = pa.client_id
)
FROM _managers
UNION ALL
FROM _admins
;
