SELECT t.id FROM df, t WHERE list_contains(CAST(df.filter.sku_keys AS VARCHAR[]), t.sku_key)
