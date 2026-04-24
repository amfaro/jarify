SELECT
   '{request_id}'        AS request_id
  ,wp.invoice_date::date AS invoice_date
  ,wp.sku_key            AS provided_sku_key
  ,wp.resolved_sku_key   AS sku_key
  ,wp.program_redemption_amount
  ,wp.amount::double     AS provided_amount
  ,wp.quantity::double   AS quantity
FROM _with_prices wp
;
