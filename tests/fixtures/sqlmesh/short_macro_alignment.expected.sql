MODEL (name @schema.scope_users, kind FULL);

SELECT
   c.scope_key
  ,ua.user_id
  ,@ds         AS run_day
  ,COUNT(*)    AS attribute_count
FROM _conditions                    c
INNER JOIN @schema.user_attributes ua ON ua.parent_client_id = c.parent_client_id AND ua.attribute = c.attribute
GROUP BY
   c.scope_key
  ,ua.user_id
  ,@ds
;
