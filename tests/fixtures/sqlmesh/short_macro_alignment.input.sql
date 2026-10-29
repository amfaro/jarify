MODEL (name @schema.scope_users, kind FULL);

select c.scope_key, ua.user_id, @ds as run_day, count(*) as attribute_count
from _conditions c
join @schema.user_attributes ua on ua.parent_client_id = c.parent_client_id and ua.attribute = c.attribute
group by c.scope_key, ua.user_id, @ds
