SELECT
   list_transform(k, lambda x: x + 1)                           AS arrow_form
  ,list_transform(k, lambda x: x + 1)                           AS keyword_form
  ,list_reduce(k, lambda acc, x: acc + x)                       AS two_params
  ,list_filter(doc -> 'items', lambda x: x > 1)                 AS json_list_argument
  ,ifnull(doc -> 'name', 'unknown')                             AS json_outside_lambda_function
  ,my_macro(k, x -> x)                                          AS user_macro_arrow
  ,[first_name, last_name].list_filter(lambda x: x IS NOT NULL) AS method_call
FROM t
;

SELECT
   columns(lambda col: NOT regexp_matches(col, 'manager_'))
FROM t
;

SELECT
   list_transform(
     k
    ,lambda x:
      format('{} {} ({}, {}, {}) since {}', x.first_name, x.last_name, x.organization_name, x.country_code, x.rep_type, x.hired_on)
  ) AS wide_body
FROM t
;
