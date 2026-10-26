SELECT
   list(nomination_id ORDER BY created_at DESC) AS short_list
  ,list_slice(list({'nomination_id': nomination_id, 'created_at': created_at, 'created_on': created_at::date} ORDER BY created_at DESC, nomination_id DESC), 0, 10) AS recent_nominations
  ,created_at::TIMESTAMPTZ AS created_at_tz
FROM nominations
GROUP BY ALL
;
