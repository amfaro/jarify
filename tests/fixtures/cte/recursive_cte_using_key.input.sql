with recursive _hierarchy using key (position_id) as (
  select position_id, parent_position_id, 0 as depth from positions where parent_position_id is null
  union
  select p.position_id, p.parent_position_id, h.depth + 1 as depth from positions p join _hierarchy h on p.parent_position_id = h.position_id
),
_pairs (a, b) using key (a, b) as materialized (select 1, 2)
select * from _hierarchy cross join _pairs
