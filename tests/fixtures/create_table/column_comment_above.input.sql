-- A comment on its own line above a column stays above it, outside the alignment
CREATE TABLE t (
  -- the key
  id int PRIMARY KEY,
  -- shown to users
  label text,
  kind my_type -- a user-defined type
)
;
