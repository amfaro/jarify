# jarify

Bespoke SQL linter and formatter for [DuckDB](https://duckdb.org), built on [sqlglot](https://github.com/tobymao/sqlglot).

Existing SQL formatters can't be configured to enforce a specific team style, and none of them are DuckDB-aware. Jarify parses SQL with the DuckDB dialect and rewrites it through an opinionated, non-configurable formatter — no style debates, consistent output everywhere.

## Quick start

No installation required. Run directly with [`uvx`](https://docs.astral.sh/uv/guides/tools/).

### From a GitHub Release (recommended)

Releases publish a pre-built wheel to the [Releases page](https://github.com/amfaro/jarify/releases). Pinning to a wheel is the fastest option because uv skips the build step:

```bash
uvx --from "https://github.com/amfaro/jarify/releases/download/v0.0.1/jarify-0.0.1-py3-none-any.whl" jarify fmt path/to/query.sql
```

### From git

Always runs the latest commit on `main` — useful during development:

```bash
uvx --from git+https://github.com/amfaro/jarify.git jarify fmt path/to/query.sql
```

Pin to a specific release tag:

```bash
uvx --from "git+https://github.com/amfaro/jarify.git@v0.0.1" jarify fmt path/to/query.sql
```

### Persistent install

```bash
uv tool install "https://github.com/amfaro/jarify/releases/download/v0.0.1/jarify-0.0.1-py3-none-any.whl"
jarify fmt path/to/query.sql
```

## Commands

### `jarify fmt` — format SQL files

```
jarify fmt [OPTIONS] [FILES]...
```

Reads each file, formats it, and writes the result back in place.

| Option | Description |
|--------|-------------|
| `-` | Read from stdin |
| `--check` | Exit non-zero if any file would change (useful in CI) |
| `--diff` | Print a unified diff instead of rewriting files |
| `--stdin-filename NAME` | Label to use in diff output when reading from stdin |

**Exit codes:** `0` = all files already formatted, `1` = files were reformatted, `2` = error.

```bash
# Format a single file
jarify fmt query.sql

# Check all .sql files without modifying them (CI mode)
jarify fmt --check **/*.sql

# Preview changes as a diff
jarify fmt --diff query.sql

# Pipe from stdin
cat query.sql | jarify fmt -
```

### `jarify lint` — lint SQL files

```
jarify lint [OPTIONS] [FILES]...
```

Reports style and semantic violations. Does not modify files.

```bash
jarify lint query.sql
```

### `jarify init` — create a config file

```bash
jarify init
```

Writes a `jarify.toml` in the current directory. Config is internal to the tool — this is primarily useful for future per-project rule overrides.

### `jarify show-config` — inspect active config

```bash
jarify show-config
```

Prints the effective configuration (syntax-highlighted TOML).

## Formatting style

Jarify enforces a single, opinionated style. There are no knobs to turn.

### Leading commas

```sql
SELECT
   manufacturer_label
  ,brand_prefix_label
  ,pack_size_label
FROM products
ORDER BY
   manufacturer_label
  ,sku_key;
```

The first column gets one extra leading space so content aligns with the `,col` lines. The same pattern applies to function arguments when they wrap.

### CTE layout

Opening paren on its own line, subsequent CTEs prefixed with a comma:

```sql
WITH _latest_version AS
(
  SELECT
     regexp_extract(file, 'version=(.{21})', 1) AS version
  FROM glob('s3://bucket/catalog/*/*')
  ORDER BY
     file DESC
  LIMIT 1
)
,_relevant_skus AS
(
  SELECT
     *
  FROM read_parquet(
     's3://bucket/dataops/*/*/relevant_skus.parquet'
    ,hive_partitioning = TRUE
    ,hive_types = {'program_supplier_key': text, 'time_frame': int}
  )
  WHERE
    time_frame = getvariable('time_frame')
)
SELECT ...
```

### Other rules

| Rule | Behaviour |
|------|-----------|
| **Keywords** | Uppercase (`SELECT`, `FROM`, `WHERE`, …) |
| **Functions** | Lowercase (`read_parquet`, `glob`, `getvariable`, …) |
| **Bare `JOIN`** | Normalized to `INNER JOIN` |
| **AND / OR chains** | Each condition on its own line |
| **`IS NOT NULL`** | Preserved as-is (not rewritten to `NOT x IS NULL`) |
| **`NULLS LAST`** | Suppressed when it matches DuckDB's default ordering |
| **`NULLS FIRST`** | Preserved when it differs from DuckDB's default |
| **Table aliases** | `AS` keyword always added (`FROM t AS t1`) |

## Lint rules

| Rule | Default | Description |
|------|---------|-------------|
| `no_select_star` | `warn` | Flag `SELECT *` (except `COUNT(*)`) |
| `no_implicit_cross_join` | `warn` | Require explicit `CROSS JOIN` keyword |
| `no_unused_cte` | `warn` | Flag CTEs that are never referenced |
| `duckdb_type_style` | `warn` | Flag non-canonical DuckDB type names |
| `duckdb_prefer_qualify` | `warn` | Prefer `QUALIFY` over subquery window filter |

## Development

Requires [mise](https://mise.jdx.dev) and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/amfaro/jarify.git
cd jarify
uv sync --all-groups

mise run test    # run tests
mise run lint    # ruff check
mise run check   # lint + test
```

### Adding a new fixture test

1. Create `tests/fixtures/<category>/<name>.input.sql` with the raw SQL
2. Run `uv run pytest tests/test_fixtures.py --update-fixtures` to generate the expected output
3. Review `tests/fixtures/<category>/<name>.expected.sql` and commit both files

### Releases

Push a `v*` tag to trigger the publish workflow. GitHub Actions builds the wheel and sdist, attaches them to a GitHub Release, and generates release notes automatically.

```bash
git tag v0.0.1
git push origin v0.0.1
```