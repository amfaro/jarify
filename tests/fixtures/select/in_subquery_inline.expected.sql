FROM offers
WHERE program_key IN (SELECT program_key FROM _programs)
;
