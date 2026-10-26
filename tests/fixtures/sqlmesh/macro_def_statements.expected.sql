MODEL (
  name s.m,
);


@DEF(source_db, 'X');
@DEF(source_schema, 'dbo');


SELECT
   id
FROM @read_parquet(@source_db, @source_schema, 'Program')
;
