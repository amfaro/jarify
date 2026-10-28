select
  g,
  bool_or(status in ('denied')) as any_denied,
  bool_and(points > 0) as all_positive,
  bool_or(active) filter (where kind = 'a') as any_active_a,
  logical_or(active) as any_active,
  bool_and(flag::boolean) as all_flagged
from t
group by g;

select id, bool_and(active) over (partition by g) as all_active_in_g from t;
