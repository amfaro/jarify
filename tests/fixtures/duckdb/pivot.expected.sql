FROM t
PIVOT(sum(amount) FOR  category IN ( 'A'
    ,'B'
,'C'))
;
