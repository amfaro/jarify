MODEL (name foo.virtual_model);

ON_VIRTUAL_UPDATE_BEGIN;
select id,status from @this_model where updated_at >= @start_dt
ON_VIRTUAL_UPDATE_END;

select id,status from raw_status
