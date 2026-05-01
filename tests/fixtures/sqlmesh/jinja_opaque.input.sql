MODEL (name foo.jinja_model);

select 1 as before_block
{% if is_incremental() %}
select bad,unformatted from raw_table
{% endif %}
JINJA_STATEMENT_BEGIN;
select {{ macro_value() }}
JINJA_END;
select {{ dim_col }} as dim from {{ ref('dim_table') }}
