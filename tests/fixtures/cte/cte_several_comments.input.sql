WITH _a /* first */ /* second */ AS (SELECT 1 AS x)
/* own-line block comment */
/* another one */
,_b AS (SELECT 2 AS y)
-- rev_seq comes from seq, so rows that still tie
-- can't pair the two differently between builds.
,_c AS (SELECT 3 AS z)
SELECT x, y, z FROM _a, _b, _c;
