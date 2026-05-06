WITH RECURSIVE _transactions AS MATERIALIZED
(
  FROM t
)
,_hint_off AS NOT MATERIALIZED
(
  FROM u
)
,_plain AS
(
  FROM v
)
SELECT
   *
FROM _transactions
INNER JOIN _hint_off USING (id)
INNER JOIN _plain USING (id)
;
