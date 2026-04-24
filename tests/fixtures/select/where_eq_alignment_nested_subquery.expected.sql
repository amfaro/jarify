SELECT
   t.*
  ,s.sku_set
  ,s.rate
FROM transactions        t
INNER JOIN _sku_set_skus s USING (sku_key)
WHERE t.transaction_type = s.transaction_type
  AND t.invoice_date BETWEEN s.start_date AND s.end_date
  AND (group_by_value IS NULL OR (to_json({'purchaser': t.purchaser})->>(SELECT concat('$.', o.group_by[1].field, '.', o.group_by[1].key) FROM offers AS o WHERE o.offer_key = offer_key)) = group_by_value)
;
