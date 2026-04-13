CREATE OR REPLACE TABLE examples
(
   transaction_id       text                    NOT NULL
  ,request_id           text                    NOT NULL
  ,participant_key      text                    NOT NULL
  ,time_frame           text                    NOT NULL
  ,program_supplier_key text                    NOT NULL
  ,properties           key_value_pair_struct[] NOT NULL DEFAULT []
  ,transaction_type     text                    NOT NULL
  ,sku_key              text                    NOT NULL
  ,uom_key              text                    NOT NULL
  ,quantity             text                    NOT NULL
  ,amount               text                    NOT NULL
  ,invoice_date         text                    NOT NULL
  ,seller_key           text
  ,purchaser            purchaser_struct

  ,PRIMARY KEY (program_supplier_key, time_frame, request_id, transaction_id)
)
;
