SELECT
   array_agg(
    DISTINCT
    (
       active_ingredient_key
      ,quantity
      ,active_ingredient_uom_key
    )::active_ingredient_struct
  )
FROM sku_composition
;
