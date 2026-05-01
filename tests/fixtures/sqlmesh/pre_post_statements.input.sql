MODEL (
  name foo.pre_post_orders,
  kind FULL,
  dialect duckdb
);

create or replace temp table _jarify_stage_orders as
select order_id,amount,ds from @input_model where ds = @run_dt;

select order_id,amount from _jarify_stage_orders where amount > 0;

drop table if exists _jarify_stage_orders;
