SELECT * EXCLUDE (sku_set_total_coverage) FROM _ordered WHERE sku_set_total_coverage > 0;
SELECT * REPLACE (col + 1 AS col) FROM _ordered;
SELECT * RENAME (old_name AS new_name) FROM _ordered;
