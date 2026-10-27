MODEL (
  name s.m,
);


/*
Notes about the model.
*/


-- Pre-statement: (re)creates the macro before the query runs.
-- NOTE: a second line of explanation.
@ensure_sql_macro('nom_profile_for');


SELECT
   a
FROM t
;
