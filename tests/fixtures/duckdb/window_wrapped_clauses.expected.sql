SELECT
   SUM(a.allocation_per_year / 12) OVER (
     PARTITION BY a.client_id, a.nomination_application_ids, a.employee_user_id
     ORDER BY m.the_month
     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  )                                                                  AS running_allocation
  ,ROW_NUMBER() OVER (PARTITION BY a.client_id ORDER BY m.the_month) AS seq
FROM a
CROSS JOIN m
;
