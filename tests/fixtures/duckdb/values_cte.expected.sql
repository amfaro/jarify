CREATE OR REPLACE MACRO get_programs_json
(
   _participant_key
  ,_time_frame
  ,_program_supplier_key
) AS
(
  WITH _qualification_types (qualification_type, style) AS
  (
    VALUES
       ('aggregated_amount',       'aggregation')
      ,('aggregated_quantity',     'aggregation')
      ,('brand_count',             'count')
      ,('property',                'property')
      ,('yoy_amount_index',        'ratio')
      ,('yoy_quantity_index',      'ratio')
      ,('share_of_wallet_percent', 'ratio')
      ,('amount_average_index',    'ratio')
  )
  SELECT
     qualification_type
    ,style
  FROM _qualification_types
)
;
