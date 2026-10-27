-- A short window stays on one line
SELECT
   SUM(x) OVER (PARTITION BY a ORDER BY b) AS s
FROM t
;

-- A long ORDER BY list puts one key per line
SELECT
   ROW_NUMBER() OVER (
     ORDER BY
        time_frame_key
       ,client_name
       ,process_type
       ,process_sub_type
       ,audience
       ,nom_detail_status_keys
       ,nom_status_key
       ,nom_team_status_key
       ,points_actually_awarded
  ) AS node_id
FROM t
;

-- A long PARTITION BY list puts one key per line; a short ORDER BY stays on its line
SELECT
   SUM(amount) OVER (
     PARTITION BY
        client_id
       ,program_id
       ,nomination_application_id
       ,employee_user_id
       ,reporting_period_key
       ,currency_code
       ,recipient_user_id
     ORDER BY created_at
  ) AS running
FROM t
;

-- Both lists long, with a frame clause
SELECT
   SUM(amount) OVER (
     PARTITION BY
        client_id
       ,program_id
       ,nomination_application_id
       ,employee_user_id
       ,reporting_period_key
       ,currency_code
       ,recipient_user_id
     ORDER BY
        created_at DESC
       ,nomination_id DESC
       ,sequence_number
       ,updated_at DESC
       ,recipient_user_id
       ,giver_user_id
       ,approver_user_id
     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running
FROM t
;
