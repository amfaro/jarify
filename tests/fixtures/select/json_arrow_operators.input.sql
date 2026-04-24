SELECT
   value ->> 'offer_key'
  ,value -> 'nested'
  ,(value->>'program_key')       AS program_key
  ,(value->'qualification_key') AS qualification_key
FROM data
;
