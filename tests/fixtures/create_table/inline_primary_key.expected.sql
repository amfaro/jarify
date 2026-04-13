CREATE TABLE orders
(
   order_id INT            NOT NULL PRIMARY KEY
  ,customer TEXT           NOT NULL
  ,total    DECIMAL(18, 3)
)
;
