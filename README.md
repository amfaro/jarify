# jarify

Bespoke SQL linter and formatter for [DuckDB](https://duckdb.org), built on [sqlglot](https://github.com/tobymao/sqlglot).

Existing SQL formatters can't be configured to enforce a specific team style, and none of them are DuckDB-aware. Jarify parses SQL with the DuckDB dialect and rewrites it through an opinionated, non-configurable formatter — no style debates, consistent output everywhere.

## Installation

```bash
uv tool install jarify
```

Or run one-off without installing:

```bash
uvx jarify fmt path/to/query.sql
```

### Upgrade

```bash
uv tool upgrade jarify
```

### Pin to a specific version

```bash
uv tool install 'jarify==0.1.0'
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

## Style and lint rules

Jarify enforces a single, opinionated style. There are no knobs to turn. See the **[SQL Style Guide](docs/sql-style-guide.md)** for the complete rule reference with bad/good examples for every formatting and lint rule.

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

Push a `v*` tag to trigger the publish workflow. GitHub Actions builds the wheel and sdist, publishes to PyPI via OIDC trusted publishing, attaches artifacts to a GitHub Release, and generates release notes automatically.

```bash
git tag v0.1.0
git push origin v0.1.0
```