{program_filter}
{example_filter}
CREATE OR REPLACE TABLE offers AS
SELECT
   o.*
FROM offers         o
INNER JOIN programs p ON o.program_key = p.program_key
;
