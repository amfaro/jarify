select
  {user_id: u.id, name: u.name} as person,
  struct_pack(user_id := u.id, name := u.name) as packed,
  STRUCT_PACK(k := 1) as upper_call,
  to_json(struct_pack(purchaser := u.purchaser)) as purchaser_json,
  struct_pack(nomination_application_id := u.nomination_application_id, nomination_application_name := u.nomination_application_name, nomination_application_label := u.nomination_application_label) as long_call,
  struct_pack(
    a := 1, -- the first field
    b := 2
  ) as commented
from u
