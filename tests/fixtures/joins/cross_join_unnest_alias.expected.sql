SELECT
   so.id
  ,t.filter_data
FROM sales_orders                                         so
CROSS JOIN UNNEST((so.incentive_data->'filters')::json[]) t(filter_data)
;
