INSERT INTO t (a, b) VALUES (1, 2);

INSERT INTO t (a, b) SELECT x, y FROM u;

INSERT INTO events (event_id, event_type, occurred_at, participant_key, program_supplier_key, payload) SELECT * FROM staged_events;

CREATE VIEW v (c, d) AS SELECT 1, 2;
