-- One row per (qualification, partition_value).
-- group_by_values is [NULL] for ungrouped programs (yielding a single
-- NULL partition) and [id1, id2, ...] for grouped programs.
SELECT
   version()
;
