SELECT
   c.client_id
  ,c.ids -- a trailing note that is longer than any column
  -- ,c.nomination_application_id_from_an_earlier_version
  ,c.rep_type_id
  ,c.a           AS x
  ,c.b           AS y
FROM t c
;
