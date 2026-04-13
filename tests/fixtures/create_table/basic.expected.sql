CREATE OR REPLACE TABLE examples
(
   transaction_id       TEXT                    NOT NULL
  ,request_id           TEXT                    NOT NULL
  ,participant_key      TEXT                    NOT NULL
  ,time_frame           TEXT                    NOT NULL
  ,program_supplier_key TEXT                    NOT NULL
  ,properties           key_value_pair_struct[] NOT NULL DEFAULT []
  ,transaction_type     TEXT                    NOT NULL
  ,sku_key              TEXT                    NOT NULL
  ,uom_key              TEXT                    NOT NULL
  ,quantity             TEXT                    NOT NULL
  ,amount               TEXT                    NOT NULL
  ,invoice_date         TEXT                    NOT NULL
  ,seller_key           TEXT
  ,purchaser            purchaser_struct

  ,PRIMARY KEY (program_supplier_key, time_frame, request_id, transaction_id)
)
;
