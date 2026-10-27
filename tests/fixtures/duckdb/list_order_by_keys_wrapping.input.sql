-- A long ORDER BY list goes below the argument, one key per line
SELECT list(nomination_id ORDER BY created_at DESC, nomination_id DESC, client_id, program_id, nomination_application_id, employee_user_id, reporting_period_key) AS ids FROM t GROUP BY ALL
;

-- A wrapped argument puts ORDER BY on its own line, lined up with the argument
SELECT id, list({'attribute': attribute, 'custom_field_label': custom_field_label, 'custom_field_type_key': custom_field_type_key, 'seq': seq, 'value': mapped_value} ORDER BY attribute, custom_field_label, seq) AS custom_field_values FROM t GROUP BY ALL
;
