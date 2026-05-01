MODEL (name foo.jinja_model);

SELECT
   1 AS before_block
;
{% if is_incremental() %}
select bad,unformatted from raw_table
{% endif %}
JINJA_STATEMENT_BEGIN;
select {{ macro_value() }}
JINJA_END;
SELECT
   {{ dim_col }} AS dim
FROM {{ ref('dim_table') }}
;
