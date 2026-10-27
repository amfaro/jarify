-- A CASE in another CASE's THEN, ELSE or WHEN is laid out under its own CASE keyword
SELECT
   CASE
     WHEN y = 1
     THEN CASE
            WHEN x = 1
            THEN 'one'
            WHEN x = 2
            THEN 'two'
            ELSE 'many'
          END
     WHEN y = 2
     THEN 'b'
   END AS in_then
  ,CASE
     WHEN y = 1
     THEN 'a'
     WHEN y = 2
     THEN 'b'
     ELSE CASE
            WHEN x = 1
            THEN 'one'
            WHEN x = 2
            THEN 'two'
            ELSE 'many'
          END
   END AS in_else
  ,CASE
     WHEN CASE
            WHEN x = 1
            THEN 'one'
            WHEN x = 2
            THEN 'two'
            ELSE 'many'
          END = 'one'
     THEN 1
     WHEN y = 2
     THEN 2
   END AS in_when
FROM t
;

-- A simple CASE in a branch, and a CASE in a simple CASE's branch
SELECT
   CASE
     WHEN y = 1
     THEN CASE k
           WHEN 1 THEN 'one'
           WHEN 2 THEN 'two'
           ELSE 'many'
         END
     WHEN y = 2
     THEN 'b'
   END AS simple_in_then
  ,CASE k
    WHEN 1 THEN CASE
                  WHEN x = 1
                  THEN 'one'
                  WHEN x = 2
                  THEN 'two'
                  ELSE 'many'
                END
    WHEN 2 THEN 'b'
  END  AS in_simple_then
FROM t
;

-- Three levels deep
SELECT
   CASE
     WHEN a = 1
     THEN CASE
            WHEN b = 1
            THEN CASE
                   WHEN c = 1
                   THEN 'x'
                   WHEN c = 2
                   THEN 'y'
                 END
            WHEN b = 2
            THEN 'z'
          END
     WHEN a = 2
     THEN 'w'
   END AS deep
FROM t
;
