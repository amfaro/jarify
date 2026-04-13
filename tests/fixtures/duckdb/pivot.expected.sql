FROM t
PIVOT(SUM(amount) FOR  category IN ( 'A'
    ,'B'
,'C'))
;
