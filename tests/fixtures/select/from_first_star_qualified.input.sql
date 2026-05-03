SELECT * EXCLUDE (sku_set_total_coverage) FROM _ordered WHERE sku_set_total_coverage > 0;
SELECT * REPLACE (col + 1 AS col, longer_col_name + 2 AS longer_col_name) FROM _ordered;
SELECT * RENAME (id AS vendor_id, name AS vendor_name) FROM _ordered;
