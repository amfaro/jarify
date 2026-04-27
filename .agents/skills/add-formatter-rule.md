---
name: add-formatter-rule
description: Use when adding or changing a formatting rule in JarifyGenerator. Ensures sqlglot defaults are audited, the override is placed correctly, tests and fixtures are added, and the style guide is updated.
---

# Add Formatter Rule

## Overview

Jarify overrides sqlglot's `DuckDB.Generator` to enforce its opinionated style. sqlglot's defaults often diverge from jarify's style — missing an override silently produces wrong output (e.g. uppercase `TRUE`/`FALSE` before `boolean_sql()` was added). This skill guards against that gap.

## Workflow

1. **Audit sqlglot's default first**

   Before writing any code, confirm what sqlglot emits for the construct you're targeting:

   ```python
   from sqlglot import parse_one
   from sqlglot.dialects import DuckDB
   print(DuckDB().generate(parse_one("<your SQL>", dialect="duckdb")))
   ```

   If the output already matches jarify style, no override is needed. If it doesn't, continue.

2. **Add the override to `JarifyGenerator`**

   All formatting overrides live in `src/jarify/generator.py`. Find the most relevant section using the section headers (e.g. `# Data types`, `# Function name casing`). Place the new method near related overrides.

   Follow the existing pattern — most overrides are one-liners:
   ```python
   def boolean_sql(self, expression: exp.Boolean) -> str:
       return "true" if expression.this else "false"
   ```

3. **Add a fixture pair**

   ```bash
   # Input file
   echo "SELECT a FROM t WHERE flag = true" > tests/fixtures/select/<name>.input.sql

   # Generate expected output
   uv run python -m pytest tests/test_fixtures.py --update-fixtures

   # Review the generated .expected.sql — confirm it matches jarify style
   ```

4. **Update existing fixtures if needed**

   Run the full suite to find fixtures that now produce different output:
   ```bash
   uv run python -m pytest tests/test_fixtures.py -v
   ```
   Regenerate any that fail due to the new rule:
   ```bash
   uv run python -m pytest tests/test_fixtures.py --update-fixtures
   ```
   Review each regenerated file to confirm the change is intentional.

5. **Update `docs/sql-style-guide.md`**

   Every formatting rule must have a documented bad/good example in `docs/sql-style-guide.md`. Place it in the Formatting Rules section, near related rules.

6. **Verify**

   ```bash
   uv run python -m pytest tests/
   ```

   All tests must pass before committing.

## Known sqlglot Defaults That Jarify Overrides

| Construct | sqlglot default | Jarify override | Method |
|-----------|----------------|-----------------|--------|
| Boolean literals | `TRUE` / `FALSE` | `true` / `false` | `boolean_sql()` |
| Data types | `TEXT`, `INT`, … | `text`, `int`, … | `datatype_sql()` |
| Aggregate/window functions | lowercase | `COUNT`, `SUM`, … | `normalize_func()` |
| Scalar functions | varies | lowercase | `normalize_func()` |
| Column expressions | trailing commas | leading commas | `expressions()` |
| Bare `JOIN` | `JOIN` | `INNER JOIN` | rule in `rules/` |
| `CASE WHEN x THEN y [ELSE z] END` | CASE WHEN form | `if(x, y[, z])` | `if_sql()` + rule in `rules/` |

When adding a new override, add it to this table.

## Guardrails

- Never assume sqlglot's output matches jarify style — always audit first.
- Do not add a `_sql()` override without a corresponding fixture and style-guide entry.
- Do not regenerate fixtures without reviewing each diff — a regenerated file that looks wrong means the override is wrong.
- If an existing expected fixture changes because of your new rule, that is intentional; review and commit it alongside the rule.

## Common Mistakes

- Adding an override but forgetting to update `docs/sql-style-guide.md` — the style guide is the authoritative reference for users and AI agents.
- Running `--update-fixtures` blindly without inspecting output — regenerated files can silently encode bugs.
- Placing a new override far from related methods — keep `boolean_sql()` near `datatype_sql()`, etc.
