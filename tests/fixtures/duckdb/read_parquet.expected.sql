FROM read_parquet('data.parquet')
WHERE
  year = 2024
;
