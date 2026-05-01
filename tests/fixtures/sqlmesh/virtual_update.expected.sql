MODEL (name foo.virtual_model);

ON_VIRTUAL_UPDATE_BEGIN;
SELECT
   id
  ,status
FROM @this_model
WHERE updated_at >= @start_dt
;
ON_VIRTUAL_UPDATE_END;

SELECT
   id
  ,status
FROM raw_status
;
