-- A commented window spec breaks into one clause per line
SELECT
   id
  ,ROW_NUMBER() OVER (
     PARTITION BY
        userId
       ,customFieldId
     ORDER BY
        id DESC -- identify the latest record if there are duplicates
   ) AS rev_seq
FROM t
;

-- Comments on PARTITION BY and ORDER BY keys, before ORDER BY, and after the frame
SELECT
  SUM(x) OVER (PARTITION BY a -- by a
               ORDER BY b) AS s1
 ,SUM(x) OVER (PARTITION BY a
               -- newest first
               ORDER BY b DESC) AS s2
 ,SUM(x) OVER (ORDER BY b ROWS BETWEEN 1 PRECEDING AND CURRENT ROW -- rolling pair
              ) AS s3
FROM t
;

-- Named windows and QUALIFY
SELECT a
FROM t
QUALIFY ROW_NUMBER() OVER (PARTITION BY a ORDER BY b DESC -- latest
        ) = 1
;

SELECT SUM(x) OVER w AS s FROM t
WINDOW w AS (PARTITION BY a -- by a
             ORDER BY b)
;

-- A window without comments stays inline
SELECT SUM(x) OVER (PARTITION BY a ORDER BY b) AS s FROM t
;
