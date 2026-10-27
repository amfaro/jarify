-- A THEN or ELSE value that doesn't fit on its line takes its own layout, its ")" under THEN
SELECT CASE WHEN a = 1 THEN (SELECT MAX(b) FROM u WHERE u.id = t.id AND u.kind = 'something long enough to wrap the line, for sure, right now') WHEN a = 2 THEN 3 ELSE (SELECT MIN(b) FROM u WHERE u.id = t.id AND u.kind = 'something else that is long enough to wrap the line, for sure') END AS v, b AS w FROM t;

-- One that fits stays on its line
SELECT CASE WHEN a = 1 THEN (SELECT MAX(b) FROM u WHERE u.id = t.id) WHEN a = 2 THEN 3 END AS v FROM t;

-- In a simple CASE the value's ")" goes under WHEN
SELECT CASE a WHEN 1 THEN (SELECT MAX(b) FROM u WHERE u.id = t.id AND u.kind = 'something long enough to wrap the line, for sure, right now') ELSE 2 END AS v FROM t;

-- So do the other lines of a wrapped call
SELECT CASE WHEN x THEN if(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa = 1, bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, cccccccccccccccc) WHEN y THEN 2 END AS v FROM t;

-- A single-branch CASE rewritten to if() measures its arguments' lines the same way
SELECT o.id, CASE WHEN o.status = 'shipped' THEN (SELECT MAX(s.shipped_at) FROM shipments s WHERE s.order_id = o.id AND s.carrier_status = 'delivered_to_customer') ELSE o.updated_at END AS last_event_at FROM orders o;
