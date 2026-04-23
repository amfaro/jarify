select
    a.id
    , a.active = true
    , b.deleted = false
from accounts as a
inner join bans as b
    on b.account_id = a.id
where a.verified = true
;
