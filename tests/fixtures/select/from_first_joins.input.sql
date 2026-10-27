FROM rpt.points_with_monetary_value p SEMI JOIN common.dates d ON d.the_date = p.the_date SEMI JOIN _clients c USING (parent_client_id);

FROM uni.users CROSS JOIN _time_frames;

FROM t p, d dd;

WITH _c AS (FROM t p SEMI JOIN d dd ON dd.x = p.x INNER JOIN e ee ON ee.y = p.y) SELECT * FROM _c;

FROM t p LEFT JOIN d dd ON dd.x = p.x SELECT p.a;

SELECT * FROM t p SEMI JOIN d dd ON dd.x = p.x;
