SELECT * FROM (VALUES (1, 'a'), (2, 'b')) v(id, name);

SELECT t.a, v.name FROM t INNER JOIN (VALUES (1, 'active'), (2, 'inactive')) v(id, name) ON v.id = t.id;

SELECT v.id FROM (VALUES (1, 'a fairly long label number one'), (2, 'a fairly long label number two'), (3, 'a fairly long label number three')) v(id, name);

SELECT * FROM (VALUES (1, 'a')) v;
