-- The CTEs and every branch of the final UNION share one AS column
with _owners as (select ou.organization_id, ou.user_id as owner_user_id from organization_users ou)
select cp.organization_id, 'margin' as category, sum(cp.margin * cp.current_units) as value
from customer_products cp join _owners o on o.organization_id = cp.organization_id group by all
union all
select rh.organization_id, 'rebate' as category, sum(rh.rebate) as value from rebate_history rh group by all;

-- A CTE whose body is a UNION shares it too
with _all as (select id as user_id from managers union all select admin_id as user_id from program_admins)
select user_id, count(*) as row_count from _all group by all;

-- Fewer than two aliases between the branches: nothing to align
select user_id from managers union select admin_id as user_id from program_admins;
