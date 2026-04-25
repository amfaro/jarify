SELECT
   level_key
  ,level_type
  ,qualifier
  -- pad parentheses with spaces so they become separate tokens
  ,str_split_regex(regexp_replace(qualifier, '([\(\)])', ' \1 ', 'g'), '\s+') AS parts
FROM _qualifiers
;
