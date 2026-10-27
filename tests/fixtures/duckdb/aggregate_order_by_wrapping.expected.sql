-- A short STRING_AGG stays inline
SELECT
   STRING_AGG(name, ', ' ORDER BY name) AS names
FROM t
GROUP BY ALL
;

-- A STRING_AGG too wide for its line puts ORDER BY on its own line, under the arguments
SELECT
   STRING_AGG(
     some_long_column_name
    ,', '
     ORDER BY another_long_column_name, a_third_long_column_name, yet_another_column_name
  ) AS v
FROM t
GROUP BY ALL
;

-- A key list that doesn't fit either puts one key per line
SELECT
   STRING_AGG(
     DISTINCT nomination_id
    ,', '
     ORDER BY
        nomination_id DESC
       ,created_at DESC
       ,client_id
       ,program_id
       ,nomination_application_id
       ,employee_user_id
       ,reporting_period_key
  ) AS ids
FROM t
GROUP BY ALL
;

-- Other aggregates with arguments before ORDER BY wrap the same way
SELECT
   ARG_MAX(
     nomination_application_name
    ,points_awarded
     ORDER BY created_at DESC, nomination_application_id, employee_user_id
  ) AS top_name
FROM t
GROUP BY ALL
;
