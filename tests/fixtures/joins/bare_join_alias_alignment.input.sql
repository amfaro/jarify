SELECT f.a, b.b, q.c FROM foo f JOIN barbaz b ON b.id = f.id JOIN q ON q.id = f.id LEFT OUTER JOIN cc c ON c.id = f.id
