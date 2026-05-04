SELECT
   list_transform(
     very_long_array_column_name_here
    ,s -> {'sku_set_id': s.sku_set_id, 'label': s.label, 'status': s.status, 'created_at': s.created_at}
  )                                                   AS sku_sets
  ,ifnull(incentive -> 'stacks', '[]'::json)::stack[] AS stacks
FROM t
;
