CREATE TABLE orders
(
   order_id int            NOT NULL PRIMARY KEY
  ,customer text           NOT NULL
  ,total    decimal(18, 3)
)
;
