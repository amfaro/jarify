SELECT
  *
FROM READ_PARQUET('data.parquet')
WHERE
  year = 2024;
