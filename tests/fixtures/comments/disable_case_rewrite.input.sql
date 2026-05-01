-- jarify: disable prefer-if-over-case
SELECT CASE WHEN a > 1 THEN 'big' ELSE 'small' END FROM t
-- jarify: enable prefer-if-over-case
