SELECT
   a.short           AS key
  ,a.much_longer_col AS label
  ,a.no_alias
  ,CASE
     WHEN a.x = 1
     THEN 'yes'
     WHEN a.x = 2
     THEN 'no'
     ELSE 'maybe'
   END              AS category
FROM t a
;
