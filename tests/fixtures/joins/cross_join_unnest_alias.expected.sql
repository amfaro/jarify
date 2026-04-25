SELECT
   so.id
  ,t.filter_data
FROM sales_orders so
CROSS JOIN UNNEST((so.incentive_data->'filters')::json[]) AS t(filter_data)
;
