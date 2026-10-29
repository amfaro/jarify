SELECT
   {'user_id': u.id, 'name': u.name}              AS person
  ,struct_pack(user_id := u.id, name := u.name)   AS packed
  ,struct_pack(k := 1)                            AS upper_call
  ,to_json(struct_pack(purchaser := u.purchaser)) AS purchaser_json
  ,struct_pack(
     nomination_application_id := u.nomination_application_id
    ,nomination_application_name := u.nomination_application_name
    ,nomination_application_label := u.nomination_application_label
  )                                               AS long_call
  ,struct_pack(
     a := 1 -- the first field
    ,b := 2
  )                                               AS commented
FROM u
;
