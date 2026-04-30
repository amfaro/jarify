SELECT json_extract_string(j, concat('$.', field_name, '.', key_name)) FROM t
