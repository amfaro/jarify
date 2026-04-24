SELECT
   *
FROM _programs          p
INNER JOIN _enrollments e ON e.participant_key = p.participant_key
WHERE p.time_frame      = _time_frame
  AND e.participant_key = _participant_key
  AND e.enabled
  AND (p.program_supplier_key = _program_supplier_key OR _program_supplier_key IS NULL)
;
