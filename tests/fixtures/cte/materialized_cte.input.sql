with recursive _transactions as materialized (select * from t),
     _hint_off as not materialized (select * from u),
     _plain as (select * from v)
select * from _transactions join _hint_off using (id) join _plain using (id)
