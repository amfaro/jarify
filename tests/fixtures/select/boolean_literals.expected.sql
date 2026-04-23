SELECT
   a.id
  ,a.active = true
  ,b.deleted = false
FROM accounts   a
INNER JOIN bans b ON b.account_id = a.id
WHERE a.verified = true
;
