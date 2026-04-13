"""SQL parsing utilities built on sqlglot."""

from __future__ import annotations

import functools
import re

import sqlglot
from sqlglot.errors import ParseError
from sqlglot.expressions import Expression

DUCKDB_DIALECT = "duckdb"


# ---------------------------------------------------------------------------
# Reserved-keyword type-cast pre-processor
# ---------------------------------------------------------------------------
# DuckDB allows user-defined types whose names are SQL reserved words, e.g.
#   COALESCE(x, []::filter[])
# sqlglot fails to parse these because it sees ``filter`` as a keyword token,
# not a type name.  Quoting them — ``::"filter"[]`` — makes sqlglot parse
# correctly; the generator then emits the unquoted ``::filter[]`` form again.


@functools.lru_cache(maxsize=1)
def _reserved_cast_re() -> re.Pattern[str]:
    """Return a compiled regex that matches ``::keyword`` cast type names
    where the keyword is a DuckDB reserved word that sqlglot cannot parse as
    an unquoted type.  Result is cached so the build only happens once per
    process.
    """
    from sqlglot.dialects.duckdb import DuckDB
    from sqlglot.tokens import TokenType

    tokenizer = DuckDB.Tokenizer()
    type_tokens = DuckDB.Parser.TYPE_TOKENS

    reserved: list[str] = []
    for kw in DuckDB.Tokenizer.KEYWORDS:
        word = kw.strip().lower()
        if not word.isalpha():
            continue
        toks = tokenizer.tokenize(word)
        if not toks:
            continue
        tt = toks[0].token_type
        # VAR = plain identifier; TYPE_TOKENS = sqlglot-recognised type tokens.
        # Both are safe as unquoted type names; everything else needs quoting.
        if tt != TokenType.VAR and tt not in type_tokens:
            reserved.append(word)

    words_pat = "|".join(re.escape(w) for w in sorted(reserved, key=len, reverse=True))
    # Match ::keyword or ::keyword[] but NOT ::keyword_something (word boundary via (?!\w))
    return re.compile(rf"::({words_pat})(\[\])?(?!\w)", re.IGNORECASE)


def _quote_reserved_cast_types(sql: str) -> str:
    """Quote reserved keywords used as cast type names so sqlglot can parse them.

    ``[]::filter[]`` → ``[]::"filter"[]``

    The generator round-trips this back to the unquoted ``::filter[]`` form.
    """

    def _replacer(m: re.Match[str]) -> str:
        return f'::"{ m.group(1)}"{m.group(2) or ""}'

    return _reserved_cast_re().sub(_replacer, sql)


def parse_sql(sql: str, dialect: str = DUCKDB_DIALECT) -> list[Expression]:
    """Parse a SQL string into a list of sqlglot expression trees.

    Raises ParseError if the SQL is invalid.  Applies a pre-processing step
    to quote DuckDB reserved keywords used as cast type names (e.g.
    ``::filter[]``) so sqlglot can handle them.
    """
    preprocessed = _quote_reserved_cast_types(sql)
    return sqlglot.parse(preprocessed, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)


def parse_sql_lenient(sql: str, dialect: str = DUCKDB_DIALECT) -> tuple[list[Expression], list[ParseError]]:
    """Parse SQL leniently, collecting errors instead of raising."""
    preprocessed = _quote_reserved_cast_types(sql)
    errors: list[ParseError] = []
    try:
        trees = sqlglot.parse(preprocessed, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)
    except ParseError:
        # Fall back to lenient parsing so we still get partial trees.
        # Use IGNORE (not WARN) to suppress sqlglot's side-effect stderr prints;
        # errors are re-captured via the RAISE pass below.
        trees = sqlglot.parse(preprocessed, read=dialect, error_level=sqlglot.ErrorLevel.IGNORE)
        # Re-parse to capture the actual errors
        try:
            sqlglot.parse(preprocessed, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)
        except ParseError as e:
            errors.append(e)
    return trees, errors
