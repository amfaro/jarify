"""SQL parsing utilities built on sqlglot."""

from __future__ import annotations

import sqlglot
from sqlglot.errors import ParseError
from sqlglot.expressions import Expression

DUCKDB_DIALECT = "duckdb"


def parse_sql(sql: str, dialect: str = DUCKDB_DIALECT) -> list[Expression]:
    """Parse a SQL string into a list of sqlglot expression trees.

    Raises ParseError if the SQL is invalid.
    """
    return sqlglot.parse(sql, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)


def parse_sql_lenient(sql: str, dialect: str = DUCKDB_DIALECT) -> tuple[list[Expression], list[ParseError]]:
    """Parse SQL leniently, collecting errors instead of raising."""
    errors: list[ParseError] = []
    try:
        trees = sqlglot.parse(sql, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)
    except ParseError:
        # Fall back to lenient parsing so we still get partial trees.
        # Use IGNORE (not WARN) to suppress sqlglot's side-effect stderr prints;
        # errors are re-captured via the RAISE pass below.
        trees = sqlglot.parse(sql, read=dialect, error_level=sqlglot.ErrorLevel.IGNORE)
        # Re-parse to capture the actual errors
        try:
            sqlglot.parse(sql, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)
        except ParseError as e:
            errors.append(e)
    return trees, errors
