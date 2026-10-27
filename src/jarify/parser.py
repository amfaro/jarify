"""SQL parsing utilities built on sqlglot."""

from __future__ import annotations

import bisect
import collections
import functools
import itertools
import re
import typing

import sqlglot
import sqlglot.expressions as _exp
from sqlglot.dialects.duckdb import DuckDB as _DuckDB
from sqlglot.errors import ParseError, TokenError
from sqlglot.expressions import Expression
from sqlglot.tokens import TokenType

DUCKDB_DIALECT = "duckdb"

# ---------------------------------------------------------------------------
# Custom DuckDB dialect - preserve bare NUMERIC/DECIMAL without injecting
# default precision/scale into the AST.
# ---------------------------------------------------------------------------
# sqlglot's DuckDB parser registers a TYPE_CONVERTERS handler for DECIMAL that
# calls build_default_decimal_type(precision=18, scale=3).  This fires for any
# bare NUMERIC or DECIMAL type (no user-supplied params) and injects (18, 3)
# into the AST, causing jarify to regenerate `decimal(18, 3)` when the
# original SQL only said `numeric` or `decimal`.  We remove that converter so
# bare types stay bare and round-trip cleanly.


def _keeping_operator_comments(parse: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:
    """Wrap a RANGE_PARSERS entry so the comments on its operator's words are kept.

    sqlglot drops the comments on `NOT` before the operator and on the
    operator itself (`IN`, `LIKE`, `BETWEEN`, `IS`, …), on the words after
    `IS` and on `BETWEEN`'s `AND`.
    """

    def _parse(self: _JarifyDuckDBParser, this: _exp.Expr | None) -> _exp.Expr | None:
        operator = self._index - 1
        result = parse(self, this)
        if result is not None:
            self._keep_operator_comments(result, operator)
        return result

    return _parse


def _marking_tilde(parse: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:
    """Wrap the `~` RANGE_PARSERS entry so its node remembers it was written as `~`."""

    def _parse(self: _JarifyDuckDBParser, this: _exp.Expr | None) -> _exp.Expr | None:
        result = parse(self, this)
        if isinstance(result, _exp.RegexpFullMatch):
            result.meta[TILDE_OPERATOR_KEY] = True
        return result

    return _parse


# Set on a RegexpFullMatch written as `a ~ b`. sqlglot reads that and a
# regexp_full_match(a, b) call to the same node, but DuckDB versions differ in
# whether `~` matches the whole string, so the generator writes `~` back.
TILDE_OPERATOR_KEY = "jarify_tilde_operator"


# The predicates RANGE_PARSERS builds that drop their operator's comments,
# besides those built by sqlglot's binary_range_parser(), such as LIKE.
_RANGE_OPERATOR_TOKENS = frozenset({TokenType.BETWEEN, TokenType.IN, TokenType.IS})


class _JarifyDuckDBParser(_DuckDB.Parser):
    RANGE_PARSERS: typing.ClassVar = {
        token_type: (
            _keeping_operator_comments(_marking_tilde(parse) if token_type == TokenType.TILDE else parse)
            if token_type in _RANGE_OPERATOR_TOKENS or getattr(parse, "__name__", "") == "_parse_binary_range"
            else parse
        )
        for token_type, parse in _DuckDB.Parser.RANGE_PARSERS.items()
    }
    TYPE_CONVERTERS: typing.ClassVar = {
        k: v for k, v in _DuckDB.Parser.TYPE_CONVERTERS.items() if k != _exp.DType.DECIMAL
    }
    # sqlglot treats bare TRANSFORM(...) as DuckDB's list-transform function and
    # rewrites it to LIST_TRANSFORM(...). DuckDB documents LIST_TRANSFORM and its
    # explicit aliases, but not a bare TRANSFORM alias; projects may define their
    # own `transform` macro. Remove the special-case parser entry so bare
    # TRANSFORM(...) round-trips as an anonymous function call.
    FUNCTIONS: typing.ClassVar = {k: v for k, v in _DuckDB.Parser.FUNCTIONS.items() if k != "TRANSFORM"}
    UNARY_PARSERS: typing.ClassVar = {
        **_DuckDB.Parser.UNARY_PARSERS,
        TokenType.NOT: lambda self: self._parse_not(),
    }

    # Comments the overrides below attach to nodes, as (node, keyword or
    # None, comment).  See parse().
    _recovered: list[tuple[_exp.Expr, str | None, str]] | None = None

    def parse(self, raw_tokens: list[typing.Any], sql: str) -> list[_exp.Expr | None]:
        # A comment the overrides recover may have been kept by sqlglot after
        # all: a caller can hold on to a token's comments while a nested parse
        # reads past it, as `( -- note` does before its condition.  Then the
        # recovered copy is dropped, and the comment stays where sqlglot put it.
        self._recovered = []
        try:
            trees = super().parse(raw_tokens, sql)
            _drop_duplicate_comments(trees, self._recovered)
        finally:
            self._recovered = None
        return trees

    def _keep(self, node: _exp.Expr, comments: list[str], *, prepend: bool = False) -> None:
        """Attach *comments*, which sqlglot dropped, to *node*."""
        comments = [comment for comment in comments if comment.strip()]
        if comments:
            node.add_comments(comments, prepend=prepend)
            if self._recovered is not None:
                self._recovered.extend((node, None, comment) for comment in comments)

    def _keep_keyword(self, node: _exp.Expr, keyword: str, comments: list[str]) -> None:
        """Keep *comments*, which sqlglot dropped, for the generator to write at *keyword* of *node*."""
        comments = [comment for comment in comments if comment.strip()]
        _set_keyword_comments(node, keyword, comments)
        if self._recovered is not None:
            self._recovered.extend((node, keyword, comment) for comment in comments)

    # sqlglot drops the comments on the keywords below: it reads a keyword's
    # comments only until it reads the next token, and for these it never
    # does.  The overrides keep them.

    def _parse_not(self) -> _exp.Not:
        # Comments written before NOT go on the Not node, like a comment
        # before any other condition; those written after it are kept for
        # the generator to write after NOT.
        before, after = self._split_comments(self._index - 1)
        not_ = self.expression(_exp.Not(this=self._parse_equality()))
        if before:
            not_.add_comments(before, prepend=True)
        _set_keyword_comments(not_, "NOT", after)
        return not_

    def _parse_qualify(self) -> _exp.Qualify | None:
        # As for WHERE and HAVING, the comments on QUALIFY go on the clause.
        if not self._match(TokenType.QUALIFY):
            return None
        comments = self._prev_comments
        return self.expression(_exp.Qualify(this=self._parse_disjunction()), comments=comments)

    def _parse_join(
        self,
        skip_join_token: bool = False,
        parse_bracket: bool = False,
        alias_tokens: typing.Collection[TokenType] | None = None,
    ) -> _exp.Join | None:
        start = self._index
        join = super()._parse_join(
            skip_join_token=skip_join_token, parse_bracket=parse_bracket, alias_tokens=alias_tokens
        )
        # The comments on ON or USING go on the join, as the comments on
        # WHERE go on the WHERE clause.
        if join is not None and (join.args.get("on") or join.args.get("using")):
            keywords = _top_level_tokens(self._tokens[start : self._index], {TokenType.ON, TokenType.USING})
            if keywords and keywords[-1].comments:
                join.add_comments(keywords[-1].comments)
        return join

    def _parse_case(self) -> _exp.Expr | None:
        start = self._index
        case = super()._parse_case()
        if not isinstance(case, _exp.Case):
            return case
        # Each WHEN / THEN keeps its comments on its branch, ELSE on the CASE.
        keywords = _top_level_tokens(
            self._tokens[start : self._index], {TokenType.WHEN, TokenType.THEN, TokenType.ELSE}
        )
        branches = case.args.get("ifs") or []
        for keyword, token_type in (("WHEN", TokenType.WHEN), ("THEN", TokenType.THEN)):
            tokens = [token for token in keywords if token.token_type == token_type]
            if len(tokens) == len(branches):
                for branch, token in zip(branches, tokens, strict=True):
                    _set_keyword_comments(branch, keyword, token.comments)
        else_tokens = [token for token in keywords if token.token_type == TokenType.ELSE]
        if else_tokens:
            _set_keyword_comments(case, "ELSE", else_tokens[-1].comments)
        return case

    def _parse_if(self) -> _exp.Expr | None:
        # `if(…)` drops the comments on IF, such as one on the line above the
        # call, and those on its closing paren, such as one written between
        # the call and its AS.  Other calls keep them.
        comments = self._prev_comments
        result = super()._parse_if()
        if result is not None:
            if comments:
                result.add_comments(comments, prepend=True)
            if self._prev.token_type == TokenType.R_PAREN:
                self._add_comments(result)
        return result

    def _parse_window(self, this: _exp.Expr | None, alias: bool = False) -> _exp.Expr | None:
        start = self._index
        result = super()._parse_window(this, alias=alias)
        # An aggregate's `FILTER (…)` drops the comments on its closing paren.
        if isinstance(result, _exp.Filter) and self._prev.token_type == TokenType.R_PAREN:
            self._add_comments(result)
        if result is not None and self._index > start:
            self._keep_window_comments(result, start)
        return result

    def _keep_window_comments(self, result: _exp.Expr, start: int) -> None:
        """Keep the comments sqlglot drops in a call's `FILTER (WHERE …)` and `OVER (…)`.

        Those on `FILTER`, its `(` and `WHERE` go after `WHERE`, kept on the
        Filter node. Those on the `)` that closes the FILTER before `OVER`,
        on `OVER` (or a named window's `AS`) and on its `(` go on the window,
        which writes them after itself.
        """
        tokens = self._tokens
        index = start
        window_tokens = []
        node: _exp.Expr | None = result
        while isinstance(node, (_exp.Window, _exp.IgnoreNulls, _exp.RespectNulls, _exp.WithinGroup)):
            node = node.this
        if isinstance(node, _exp.Filter) and tokens[index].token_type == TokenType.FILTER:
            where = node.expression
            comments = [*tokens[index].comments, *tokens[index + 1].comments]
            if isinstance(where, _exp.Where):
                comments.extend(where.pop_comments())
            self._keep_keyword(node, "WHERE", _unkept(result, comments))
            closing = _closing_paren(tokens, index + 1, self._index)
            if closing is None:
                return
            window_tokens.append(tokens[closing])
            index = closing + 1
        if not isinstance(result, _exp.Window) or index >= self._index:
            return
        # The `)` closing a FILTER, then `OVER` or `AS`, then `(`.
        if tokens[index].token_type in (*self.WINDOW_BEFORE_PAREN_TOKENS, TokenType.ALIAS):
            window_tokens.append(tokens[index])
            index += 1
        if index < self._index and tokens[index].token_type == TokenType.L_PAREN:
            window_tokens.append(tokens[index])
        self._keep(result, _unkept(result, [c for token in window_tokens for c in token.comments]))

    def _keep_operator_comments(self, result: _exp.Expr, operator: int) -> None:
        """Keep the comments on the words of the predicate operator at token *operator*.

        Each word's comments are kept for that word on the predicate, which
        writes them after the word: a `NOT` before the operator, the operator
        itself, the words after `IS` (`NOT`, `DISTINCT`, `FROM`) and
        `BETWEEN`'s `SYMMETRIC` and `AND`. Those on `ESCAPE` go on the Escape
        node.
        """
        tokens = self._tokens
        following = tokens[operator + 1 : self._index]
        operator_token = tokens[operator]
        words = [(operator_token.text.upper().split()[-1], operator_token)]
        if operator > 0 and tokens[operator - 1].token_type == TokenType.NOT:
            words.insert(0, ("NOT", tokens[operator - 1]))
        if operator_token.token_type == TokenType.IS:
            for token in following:
                if token.text.upper() not in _IS_WORDS:
                    break
                words.append((token.text.upper(), token))
        elif operator_token.token_type == TokenType.BETWEEN:
            if following and following[0].text.upper() in _BETWEEN_FLAGS:
                words.append((following[0].text.upper(), following[0]))
            and_ = _top_level_tokens(following, {TokenType.AND})
            if and_:
                words.append(("AND", and_[0]))

        predicate = result.this if isinstance(result, (_exp.Escape, _exp.Not)) else result
        unwritten = []
        for word, token in words:
            comments = _unkept(result, token.comments)
            if isinstance(predicate, _KEYWORD_PREDICATES) or predicate.meta.get(TILDE_OPERATOR_KEY):
                self._keep_keyword(predicate, word, comments)
            else:
                unwritten.extend(comments)
        if unwritten:
            # jarify writes the other operators as calls or as symbols: the
            # comments go on the right operand.
            operand = predicate.args.get("expression") if isinstance(predicate, _exp.Expr) else None
            self._keep(operand if isinstance(operand, _exp.Expr) else result, unwritten, prepend=True)
        escape = _top_level_tokens(following, {TokenType.ESCAPE}) if isinstance(result, _exp.Escape) else []
        if escape:
            self._keep_keyword(result, "ESCAPE", _unkept(result, escape[-1].comments))

    def _parse_using_identifiers(self) -> list[_exp.Expr]:
        # sqlglot keeps a USING column's identifier and drops the column node,
        # with the comments written after it.  Carry them over.
        def _parse_column_as_identifier() -> _exp.Expr | None:
            this = self._parse_column()
            if isinstance(this, _exp.Column):
                identifier = this.this
                if this.comments and isinstance(identifier, _exp.Expr):
                    identifier.add_comments(this.comments)
                return identifier
            return this

        return self._parse_wrapped_csv(_parse_column_as_identifier, optional=True)

    def _parse_csv(
        self, parse_method: typing.Callable[[], typing.Any], sep: TokenType = TokenType.COMMA
    ) -> list[typing.Any]:
        # The comments written after an opening bracket, before the first item
        # (`coalesce( -- note`, `IN ( -- note`, `{ -- note`), are dropped when
        # the item is parsed.  They go on the first item.
        opening = self._index - 1 if self._prev_comments and self._prev.token_type in _OPENING_BRACKETS else None
        items = super()._parse_csv(parse_method, sep=sep)
        if opening is not None and items:
            self._keep_after_opening(opening, items[0])
        return items

    def _keep_after_opening(self, opening: int, item: typing.Any) -> None:
        """Put the comments written after the opening bracket at token *opening* on *item*, its first item."""
        if not isinstance(item, _exp.Expr) or self._tokens[opening].token_type not in _OPENING_BRACKETS:
            return
        self._keep(item, _unkept(item, self._split_comments(opening)[1]), prepend=True)

    def _parse_function_call(self, *args: typing.Any, **kwargs: typing.Any) -> _exp.Expr | None:
        paren = self._index + 1 if self._next.token_type == TokenType.L_PAREN else None
        result = super()._parse_function_call(*args, **kwargs)
        # A call parsed by its own parser, such as CAST, drops the comments
        # after its `(`; they go on its first argument.  (_parse_csv keeps
        # those of the other calls.)
        if result is not None and paren is not None and self._tokens[paren].comments:
            call = result
            while isinstance(call, (_exp.Window, _exp.Filter, _exp.IgnoreNulls, _exp.RespectNulls)):
                call = call.this
            # The first argument's first operand: `a` in `CAST(a + b AS int)`.
            first = call.this if isinstance(call, _exp.Expr) else None
            while isinstance(first, _exp.Binary) and isinstance(first.this, _exp.Expr):
                first = first.this
            # A call without arguments, such as ROW_NUMBER(), writes them after itself.
            self._keep(
                first if isinstance(first, _exp.Expr) else result,
                _unkept(result, self._split_comments(paren)[1]),
                prepend=True,
            )
        return result

    def _parse_value(self, values: bool = True) -> _exp.Tuple | None:
        # A comment on its own line before a VALUES row's `(` goes on the row.
        # Those on `DISTINCT ON` and before its `(` are kept on its list for
        # the generator to write after ON.  sqlglot drops them.
        opening = self._index if self._curr.token_type == TokenType.L_PAREN else None
        distinct_on = (
            not values
            and self._index >= 2
            and self._prev.token_type == TokenType.ON
            and self._tokens[self._index - 2].token_type in self.DISTINCT_TOKENS
        )
        keywords = [*self._tokens[self._index - 2].comments, *self._prev.comments] if distinct_on else []
        row = super()._parse_value(values=values)
        if row is not None:
            before = _unkept(row, self._split_comments(opening)[0] if opening is not None else [])
            if distinct_on:
                self._keep_keyword(row, "ON", _unkept(row, keywords) + before)
            else:
                self._keep(row, before, prepend=True)
        return row

    def _parse_derived_table_values(self, allow_value_synonym: bool = False) -> _exp.Values | None:
        start = self._index
        values = super()._parse_derived_table_values(allow_value_synonym=allow_value_synonym)
        if not isinstance(values, _exp.Values):
            return values
        tokens = self._tokens
        # The comments on `VALUES` (and on the `(` of `(VALUES …)`) go after
        # VALUES.
        keyword = tokens[start : start + (2 if tokens[start].token_type == TokenType.L_PAREN else 1)]
        self._keep_keyword(values, "VALUES", _unkept(values, [c for token in keyword for c in token.comments]))
        # A comment on its own line before the comma between two rows goes on
        # the row after the comma, where it is written above that row.
        # sqlglot puts it on the row before.
        rows = values.expressions
        commas = _top_level_indices(tokens, start + len(keyword), self._index, {TokenType.COMMA})
        for comma, (row, next_row) in zip(commas, itertools.pairwise(rows), strict=False):
            before = {id(c) for c in self._split_comments(comma)[0]}
            moved = [c for c in row.comments or [] if id(c) in before]
            if moved:
                row.comments = [c for c in row.comments if id(c) not in before]
                next_row.add_comments(moved, prepend=True)
        return values

    def _parse_bracket(self, this: _exp.Expr | None = None) -> _exp.Expr | None:
        # A comment on its own line before a list or struct literal's opening
        # bracket goes on the literal, as one before a `(` goes on its
        # parentheses.  sqlglot drops it.
        opening = self._index if this is None and self._curr.token_type in _OPENING_BRACKETS else None
        result = super()._parse_bracket(this)
        if opening is not None and result is not None:
            literal = result
            while isinstance(literal, _exp.Bracket) and isinstance(literal.this, _exp.Expr):
                literal = literal.this  # `[1, 2][1]` subscripts the literal
            self._keep(literal, _unkept(result, self._split_comments(opening)[0]), prepend=True)
        return result

    def _parse_slice(self, this: _exp.Expr | None) -> _exp.Expr | None:
        # The comments on a struct entry's or a slice's `:` go on the value
        # after it.  sqlglot drops them.
        colon = self._index if self._curr.token_type == TokenType.COLON else None
        result = super()._parse_slice(this)
        if colon is not None and isinstance(result, _exp.Slice) and isinstance(result.expression, _exp.Expr):
            self._keep(result.expression, _unkept(result, self._tokens[colon].comments), prepend=True)
        return result

    def _kv_to_prop_eq(self, expressions: list[_exp.Expr], parse_map: bool = False) -> list[_exp.Expr]:
        # Struct entries are rebuilt as `key := value` nodes, which drops the
        # comments on the entry (such as one after its comma) and on its key.
        # Carry them over.  Keep the comments sqlglot is holding for the
        # struct, too: the first rebuilt entry would take them.
        keys = [e.args.get("alias") if isinstance(e, _exp.Alias) else e.this for e in expressions]
        key_comments = [list(key.comments or []) if isinstance(key, _exp.Expr) else [] for key in keys]
        held, self._prev_comments = self._prev_comments, []
        try:
            entries = super()._kv_to_prop_eq(expressions, parse_map=parse_map)
        finally:
            self._prev_comments = held
        for old, new, key, comments in zip(expressions, entries, keys, key_comments, strict=True):
            if new is not old and old.comments:
                new.add_comments(old.comments)
            new_key = new.this if isinstance(new, _exp.PropertyEQ) else None
            if isinstance(new_key, _exp.Expr) and new_key is not key and comments:
                new_key.add_comments(_unkept(new, comments))
        return entries

    def _replace_lambda(self, node: _exp.Expr | None, expressions: list[_exp.Expr]) -> _exp.Expr | None:
        # sqlglot rewrites a column naming a lambda parameter (`x.key` in
        # `lambda x: x.key`) to its identifiers, dropping the column node with
        # its comments.  Move them to the last identifier, which is kept.
        if node is not None:
            names = {e.name for e in expressions}
            for column in node.find_all(_exp.Column):
                if column.comments and column.parts and column.parts[0].name in names:
                    column.parts[-1].add_comments(column.pop_comments())
        return super()._replace_lambda(node, expressions)

    def _parse_window_clause(self) -> list[_exp.Expr] | None:
        # sqlglot drops the comments on WINDOW; they go above it.
        comments = self._curr.comments if self._curr.token_type == TokenType.WINDOW else []
        windows = super()._parse_window_clause()
        if windows:
            self._keep_keyword(windows[0], "WINDOW", _unkept(windows[0], comments))
        return windows

    def parse_set_operation(self, this: _exp.Expr | None, consume_pipe: bool = False) -> _exp.Expr | None:
        start = self._index
        operation = super().parse_set_operation(this, consume_pipe=consume_pipe)
        # sqlglot keeps the comments on UNION, EXCEPT or INTERSECT, but drops
        # those on the words after it, such as ALL or BY NAME.
        if isinstance(operation, _exp.SetOperation):
            tokens = self._tokens[start : self._index]
            keyword = next((i for i, token in enumerate(tokens) if token.token_type in self.SET_OPERATIONS), None)
            for token in tokens[keyword + 1 :] if keyword is not None else []:
                if token.text.upper() not in _SET_OPERATION_MODIFIERS:
                    break
                operation.add_comments(token.comments)
        return operation

    def _parse_subquery(self, this: _exp.Expr | None, parse_alias: bool = True) -> _exp.Subquery | None:
        # A subquery in FROM or JOIN loses the comments on its closing paren
        # when an alias follows.  Those written on their own line before the
        # paren are kept to end the body; those after it go on the subquery.
        closing = bool(self._prev_comments) and self._prev.token_type == TokenType.R_PAREN
        before, after = self._split_comments(self._index - 1) if closing else ([], [])
        if closing:
            self._prev_comments = []
        subquery = super()._parse_subquery(this, parse_alias=parse_alias)
        if closing and subquery is not None:
            _set_keyword_comments(subquery, ")", before)
            if after:
                subquery.add_comments(after)
        return subquery

    def _split_comments(self, index: int) -> tuple[list[str], list[str]]:
        """Split the comments on token *index* into those written before it and those after it.

        The tokenizer gives a token the comments that start on the lines
        between it and the previous token, and those that start on its own
        line after it.
        """
        token = self._tokens[index]
        gap_start = self._tokens[index - 1].end + 1 if index > 0 else 0
        gap = self.sql[gap_start : token.start]
        position = before = 0
        for comment in token.comments:
            for text in (f"--{comment}", f"/*{comment}*/"):
                found = gap.find(text, position)
                if found != -1:
                    position = found + len(text)
                    before += 1
                    break
            else:
                break
        return token.comments[:before], token.comments[before:]

    def _parse_select_query(self, *args: typing.Any, **kwargs: typing.Any) -> _exp.Expr | None:
        # The FROM token of a FROM-first query (`FROM t`, `FROM t SELECT a`)
        # holds the comments written above the query.  sqlglot hands them to
        # the From clause, then drops that clause when it builds the query as
        # `SELECT * FROM t`, deleting the comments; after `FROM t SELECT a` it
        # keeps them on the From clause, which generates after the SELECT list.
        # Put them on the query instead, where a comment above `SELECT` goes.
        from_token = self._curr if self._curr and self._curr.token_type == TokenType.FROM else None
        comments = list(from_token.comments) if from_token else []
        query = super()._parse_select_query(*args, **kwargs)
        if not comments:
            return query

        select = query
        while isinstance(select, _exp.SetOperation):
            select = select.this
        if isinstance(select, _exp.Select):
            from_ = select.args.get("from_")
            if from_ is not None and from_.comments == comments:
                from_.pop_comments()
            select.add_comments(comments, prepend=True)
        return query

    def _parse_cte(self) -> _exp.CTE | _exp.FunctionSpecification | None:
        start = self._index
        cte = super()._parse_cte()
        if not isinstance(cte, _exp.CTE):
            return cte

        # sqlglot keeps the comments on a CTE's AS but drops those between AS
        # and the body's opening paren (`_a AS -- note` survives, `_a AS
        # MATERIALIZED -- note` and an own-line comment before `(` don't).
        # Attach them to the CTE, marked so the generator writes them after AS.
        comments = _comments_before_cte_body(self._tokens[start : self._index])
        if comments:
            cte.add_comments(comments)
            cte.meta[CTE_COMMENTS_AFTER_AS] = comments

        # The CTE takes the comments of the `)` that closes its body, unless it
        # already took comments from its AS.  Then sqlglot leaves them to the
        # next node it builds: the WITH clause, which writes them above the
        # statement, or nothing when a comma follows, which deletes them.
        if self._prev_comments and self._prev.token_type == TokenType.R_PAREN:
            cte.add_comments(self._prev_comments)
            self._prev_comments = []
        return cte


# Meta key on a CTE node: comments written between its AS and the body's "(".
CTE_COMMENTS_AFTER_AS = "jarify_comments_after_as"

# Meta key for comments on a keyword that sqlglot drops, which the generator
# writes at that keyword: {keyword: comments}.  On a Not node, "NOT" holds
# those written after NOT; on a CASE branch (an If node), "WHEN" and "THEN";
# on a Case node, "ELSE"; on a Subquery, ")" holds those written on their own
# line before its closing paren.  On a predicate (`IN`, `BETWEEN`, `LIKE`,
# `IS`, …), each word of its operator holds the comments written on it, and
# "AND" those on BETWEEN's AND; on an Escape, "ESCAPE".  On a Filter, "WHERE"
# holds those on FILTER, its "(" and WHERE; on the first window of a WINDOW
# clause, "WINDOW"; on a Values node, "VALUES"; on DISTINCT ON's list, "ON"
# those on DISTINCT and ON.  They are not in the node's comments, which the
# generator writes after the node.
KEYWORD_COMMENTS = "jarify_keyword_comments"


def keyword_comments(node: _exp.Expr, keyword: str) -> list[str]:
    """Return the comments the parser kept for *keyword* on *node*."""
    return (node.meta_get(KEYWORD_COMMENTS) or {}).get(keyword, [])


def all_keyword_comments(node: _exp.Expr) -> list[str]:
    """Return the comments the parser kept for all keywords of *node*."""
    return [comment for comments in (node.meta_get(KEYWORD_COMMENTS) or {}).values() for comment in comments]


# Words that can follow UNION, EXCEPT or INTERSECT before the next query.
_SET_OPERATION_MODIFIERS = frozenset({"ALL", "DISTINCT", "BY", "NAME", "STRICT", "CORRESPONDING"})


# Words after IS, and BETWEEN's flags, whose comments a predicate keeps.
_IS_WORDS = frozenset({"NOT", "DISTINCT", "FROM"})
_BETWEEN_FLAGS = frozenset({"SYMMETRIC", "ASYMMETRIC"})

_OPENING_BRACKETS = frozenset({TokenType.L_PAREN, TokenType.L_BRACKET, TokenType.L_BRACE})

# The predicates jarify writes with their operator, which keep its comments
# by word.
_KEYWORD_PREDICATES = (
    _exp.In,
    _exp.Between,
    _exp.Is,
    _exp.Like,
    _exp.ILike,
    _exp.Glob,
    _exp.SimilarTo,
    _exp.NullSafeEQ,
    _exp.NullSafeNEQ,
)


def _set_keyword_comments(node: _exp.Expr, keyword: str, comments: list[str]) -> None:
    comments = [comment for comment in comments if comment.strip()]
    if comments:
        node.meta.setdefault(KEYWORD_COMMENTS, {}).setdefault(keyword, []).extend(comments)


def _unkept(node: _exp.Expr, comments: list[str]) -> list[str]:
    """Return the *comments* that *node* and its descendants don't hold yet.

    Comments are told apart by identity: each is the string the tokenizer
    read, so one written twice with the same text is still two comments.
    """
    if not comments:
        return []
    held = {id(c) for n in node.walk() for c in [*(n.comments or []), *all_keyword_comments(n)]}
    return [c for c in comments if id(c) not in held]


def _drop_duplicate_comments(trees: list[_exp.Expr | None], recovered: list[tuple[_exp.Expr, str | None, str]]) -> None:
    """Remove each *recovered* comment from its node when the trees hold it elsewhere too."""
    if not recovered:
        return
    counts: collections.Counter[int] = collections.Counter(
        id(c)
        for tree in trees
        if tree is not None
        for node in tree.walk()
        for c in [*(node.comments or []), *all_keyword_comments(node)]
    )
    for node, keyword, comment in recovered:
        if counts[id(comment)] < 2:
            continue
        held = keyword_comments(node, keyword) if keyword is not None else node.comments or []
        index = next((i for i, c in enumerate(held) if c is comment), None)
        if index is not None:
            del held[index]
            counts[id(comment)] -= 1


def _top_level_indices(tokens: list[typing.Any], start: int, end: int, types: set[TokenType]) -> list[int]:
    """Return the indices of the tokens of *types* in ``tokens[start:end]`` outside parens and nested CASEs.

    The search stops at a closing paren or END that has no opening one in the range.
    """
    found = []
    depth = 0
    for index in range(start, end):
        token_type = tokens[index].token_type
        if token_type in (TokenType.L_PAREN, TokenType.CASE):
            depth += 1
        elif token_type in (TokenType.R_PAREN, TokenType.END):
            depth -= 1
            if depth < 0:
                break
        elif depth == 0 and token_type in types:
            found.append(index)
    return found


def _top_level_tokens(tokens: list[typing.Any], types: set[TokenType]) -> list[typing.Any]:
    """Return the tokens of *types* in *tokens* that are outside parens and nested CASEs."""
    return [tokens[index] for index in _top_level_indices(tokens, 0, len(tokens), types)]


def _closing_paren(tokens: list[typing.Any], opening: int, end: int) -> int | None:
    """Return the index of the ``)`` that closes the ``(`` at *opening*, before *end*."""
    depth = 0
    for index in range(opening, end):
        if tokens[index].token_type == TokenType.L_PAREN:
            depth += 1
        elif tokens[index].token_type == TokenType.R_PAREN:
            depth -= 1
            if depth == 0:
                return index
    return None


def _comments_before_cte_body(tokens: list[typing.Any]) -> list[str]:
    """Return the comments on the tokens after a CTE's AS, up to the body's opening paren."""
    as_index = next((i for i, token in enumerate(tokens) if token.token_type == TokenType.ALIAS), None)
    if as_index is None:
        return []
    comments: list[str] = []
    for token in tokens[as_index + 1 :]:
        comments.extend(token.comments)
        if token.token_type == TokenType.L_PAREN:
            break
    return comments


class _JarifyDuckDB(_DuckDB):
    Parser = _JarifyDuckDBParser


_JARIFY_DIALECT: type[_DuckDB] = _JarifyDuckDB

# ---------------------------------------------------------------------------
# Rust format-string placeholder handling
# ---------------------------------------------------------------------------
# SQL files used as Rust format-string templates may contain placeholders like
# {where_clause} that are substituted at runtime.  These are not valid SQL, so
# we mask them before handing off to sqlglot, then restore them afterward.
#
# Pattern: {identifier} where the identifier starts with a letter/underscore
# and has no colon (which would indicate a DuckDB struct key, e.g. {key: v}).
#
# Two masking strategies are applied depending on line context:
#   • Line-level placeholder (whole line is just the placeholder):
#       → SQL block comment: /* __J_RFP_N__ */
#       A block comment is valid anywhere between SQL clauses.
#   • Inline placeholder (placeholder shares a line with other SQL tokens):
#       → Valid SQL identifier: __jrfpN__
#       An identifier is valid anywhere a name or expression is expected.

_RUST_FMT_RE = re.compile(r"\{[A-Za-z_]\w*\}")
_RUST_FMT_LINE_RE = re.compile(r"^\s*\{[A-Za-z_]\w*\}\s*$")
_AS_TRAILING_RE = re.compile(r"\bAS$", re.IGNORECASE)


def _mask_rust_fmt_placeholders(sql: str) -> tuple[str, dict[str, str]]:
    """Replace Rust format placeholders with syntactically valid SQL tokens.

    Used by the linter so placeholder tokens do not trigger parse errors.
    Returns ``(masked_sql, {marker: original_placeholder})``.
    The mapping is empty when no placeholders are present.

    Two strategies by line context:
    - Whole-line placeholder → SQL block comment (valid between clauses)
    - Inline placeholder    → dummy identifier  (valid as name/expression)
    """
    mapping: dict[str, str] = {}
    seq = [0]

    def _next_marker(placeholder: str, *, inline: bool) -> str:
        n = seq[0]
        seq[0] += 1
        if inline:
            base = f"__jrfp{n}__"
            # Pad to original length so string-literal widths are preserved
            # during AS-alignment computation (see _compute_as_align_width).
            extra = max(0, len(placeholder) - len(base))
            marker = base + "_" * extra
        else:
            marker = f"/* __J_RFP_{n}__ */"
        mapping[marker] = placeholder
        return marker

    result_lines: list[str] = []
    for line in sql.splitlines(keepends=True):
        if _RUST_FMT_LINE_RE.match(line):
            m = _RUST_FMT_RE.search(line)
            assert m is not None
            result_lines.append(line.replace(m.group(0), _next_marker(m.group(0), inline=False)))
        else:
            result_lines.append(_RUST_FMT_RE.sub(lambda m: _next_marker(m.group(0), inline=True), line))

    return "".join(result_lines), mapping


def _unmask_rust_fmt_placeholders(sql: str, mapping: dict[str, str]) -> str:
    """Restore Rust format placeholders from their masked tokens."""
    for marker, original in mapping.items():
        sql = sql.replace(marker, original)
    return sql


def _extract_ctas_body_placeholders(sql: str) -> tuple[str, dict[str, str]]:
    """Replace whole-line placeholders that serve as a CTAS body with dummy markers.

    A placeholder is a CTAS body when it immediately follows a line ending with
    the keyword ``AS`` (case-insensitive).  The dummy body ``SELECT * FROM
    __J_CTAS_BODY_N__`` lets sqlglot parse a complete, valid CTAS so neither
    the ``AS`` keyword nor surrounding structure is dropped.

    Returns ``(modified_sql, {marker: original_placeholder_line})``.  When no
    such pattern exists the SQL is returned unchanged with an empty mapping.
    """
    ctas_body_map: dict[str, str] = {}
    counter = 0
    lines = sql.splitlines(keepends=True)
    result: list[str] = []

    for i, line in enumerate(lines):
        if _RUST_FMT_LINE_RE.match(line):
            # Find the previous non-blank line to check for a trailing AS.
            prev_content = ""
            for j in range(i - 1, -1, -1):
                stripped = lines[j].strip()
                if stripped:
                    prev_content = stripped
                    break
            if _AS_TRAILING_RE.search(prev_content):
                marker = f"__J_CTAS_BODY_{counter}__"
                ctas_body_map[marker] = line.rstrip("\r\n")
                result.append(f"SELECT * FROM {marker}\n")
                counter += 1
                continue
        result.append(line)

    return "".join(result), ctas_body_map


def _restore_ctas_body_placeholders(sql: str, ctas_body_map: dict[str, str]) -> str:
    """Restore CTAS body placeholders from their dummy markers.

    Replaces the entire formatted line that contains a CTAS body marker with
    the original placeholder text.
    """
    if not ctas_body_map:
        return sql
    lines = sql.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        replaced = False
        for marker, original in ctas_body_map.items():
            if marker in line:
                result.append(original + "\n")
                replaced = True
                break
        if not replaced:
            result.append(line)
    return "".join(result)


def _extract_line_rust_fmt_placeholders(
    sql: str,
) -> tuple[str, list[tuple[list[str], list[str], str | None, str | None]]]:
    """Strip whole-line Rust format placeholder lines from ``sql``.

    Used by the formatter so the stripped SQL can be formatted normally, then
    the placeholders can be re-inserted at the correct positions afterward.

    Returns ``(stripped_sql, [(group, trailing_blanks, anchor, prev_anchor), ...])``.
    *group* is a list of one or more consecutive placeholder lines (their full
    text, leading whitespace preserved).  *trailing_blanks* is a list of blank
    lines that immediately follow the group — they are consumed here so the
    formatter does not strip them as leading whitespace, and re-emitted by
    ``_reinsert_line_rust_fmt_placeholders``.  *anchor* is the stripped text
    of the first non-blank, non-placeholder line after the group; it is
    ``None`` when no such line exists.  *prev_anchor* is the stripped text of
    the last non-blank, non-placeholder line before the group; it is ``None``
    when no such line exists.  When *anchor* text is not unique in the
    formatted SQL (e.g. a bare ``)``) *prev_anchor* disambiguates which
    occurrence to use.  Grouping consecutive placeholders together ensures they
    are re-inserted in their original order before the same anchor occurrence.
    """
    lines = sql.splitlines(keepends=True)
    result_lines: list[str] = []
    insertions: list[tuple[list[str], list[str], str | None, str | None]] = []

    i = 0
    while i < len(lines):
        if _RUST_FMT_LINE_RE.match(lines[i]):
            # Capture the last non-blank, non-placeholder line before the group
            # so re-insertion can disambiguate when the same anchor text appears
            # multiple times in the formatted SQL (e.g. bare ")" after every CTE).
            prev_anchor: str | None = None
            for j in range(len(result_lines) - 1, -1, -1):
                candidate = result_lines[j].strip()
                if candidate and not _RUST_FMT_LINE_RE.match(result_lines[j]):
                    prev_anchor = candidate
                    break
            # Collect all adjacent placeholder lines into one group so they
            # are re-inserted together (preserving relative order) before a
            # single anchor occurrence.
            group: list[str] = []
            while i < len(lines) and _RUST_FMT_LINE_RE.match(lines[i]):
                m = _RUST_FMT_RE.search(lines[i])
                assert m is not None
                group.append(lines[i].rstrip("\r\n"))
                i += 1
            # Consume blank lines that immediately follow the placeholder
            # group.  Without this, the formatter receives SQL beginning with
            # blank lines and strips them, making fmt non-idempotent on files
            # that separate a placeholder block from the first SQL statement
            # with a blank line.
            trailing_blanks: list[str] = []
            while i < len(lines) and not lines[i].strip():
                trailing_blanks.append(lines[i])
                i += 1
            anchor: str | None = None
            for j in range(i, len(lines)):
                candidate = lines[j].strip()
                if candidate and not _RUST_FMT_LINE_RE.match(lines[j]):
                    anchor = candidate
                    break
            insertions.append((group, trailing_blanks, anchor, prev_anchor))
        else:
            result_lines.append(lines[i])
            i += 1

    return "".join(result_lines), insertions


def _reinsert_line_rust_fmt_placeholders(
    sql: str,
    insertions: list[tuple[list[str], list[str], str | None, str | None]],
) -> str:
    """Re-insert whole-line placeholder groups into formatted SQL.

    Each group is inserted immediately before the first occurrence of its
    anchor line (compared after stripping whitespace), preserving all lines in
    the group in their original order.  Trailing blank lines recorded during
    extraction are emitted after the group and before the anchor.  Groups with
    no anchor are appended at the end.

    When a group has a *prev_anchor* (the last non-blank line before the
    placeholder in the original SQL), an anchor-line match is only accepted
    when the most recently seen non-blank line in the output also matches
    *prev_anchor*.  This disambiguates generic anchor text such as a bare
    ``)``) that appears after every CTE block.
    """
    if not insertions:
        return sql

    lines = sql.splitlines(keepends=True)
    # Work through groups in order; pop the first matching anchor each time so
    # that two groups with the same anchor text land before different
    # occurrences of that anchor in the formatted SQL.
    pending = list(insertions)
    result: list[str] = []
    last_non_blank: str | None = None

    for line in lines:
        stripped = line.strip()
        for idx, (group, trailing_blanks, anchor, prev_anchor) in enumerate(pending):
            if anchor is not None and stripped == anchor:
                # When prev_anchor is set, only accept this occurrence of
                # anchor if the preceding non-blank output line matches it.
                # This prevents a placeholder from landing in an earlier CTE
                # that happens to close with the same token (e.g. ")").
                if prev_anchor is not None and last_non_blank != prev_anchor:
                    continue
                for placeholder in group:
                    result.append(placeholder + "\n")
                result.extend(trailing_blanks)
                pending.pop(idx)
                break
        if stripped:
            last_non_blank = stripped
        result.append(line)

    # Append any remaining (no-anchor) groups before the trailing newline
    for group, trailing_blanks, _, __ in pending:
        for placeholder in group:
            result.append(placeholder + "\n")
        result.extend(trailing_blanks)

    return "".join(result)


# ---------------------------------------------------------------------------
# Rewriting code only
# ---------------------------------------------------------------------------
# The pre-processing below rewrites words in the SQL text before it's parsed.
# A comment's or a string literal's text must stay as written, so it rewrites
# only the text of the tokens outside literals.

_LITERAL_TOKEN_TYPES = frozenset(
    {
        TokenType.STRING,
        TokenType.IDENTIFIER,  # a quoted identifier
        TokenType.BIT_STRING,
        TokenType.HEX_STRING,
        TokenType.BYTE_STRING,
        TokenType.NATIONAL_RAW_STRING,
        TokenType.NATIONAL_STRING,
        TokenType.RAW_STRING,
        TokenType.HEREDOC_STRING,
        TokenType.UNICODE_STRING,
    }
)


def _sub_in_code(pattern: re.Pattern[str], repl: str | typing.Callable[[re.Match[str]], str], sql: str) -> str:
    """Substitute *pattern* in *sql*, except in comments, string literals and quoted identifiers.

    A match counts when it lies within a run of tokens that aren't literals,
    with nothing between them: comments and whitespace are between tokens.
    When the SQL can't be tokenized, every match is substituted.
    """
    if not pattern.search(sql):
        return sql
    try:
        tokens = _JarifyDuckDB().tokenize(sql)
    except TokenError:
        return pattern.sub(repl, sql)
    runs: list[list[int]] = []  # [start, end) of each run of adjacent code tokens
    for token in tokens:
        if token.token_type in _LITERAL_TOKEN_TYPES:
            continue
        if runs and runs[-1][1] == token.start:
            runs[-1][1] = token.end + 1
        else:
            runs.append([token.start, token.end + 1])
    starts = [start for start, _ in runs]

    def _replace(match: re.Match[str]) -> str:
        run = bisect.bisect_right(starts, match.start()) - 1
        if run < 0 or match.end() > runs[run][1]:
            return match.group(0)
        return repl(match) if callable(repl) else match.expand(repl)

    return pattern.sub(_replace, sql)


# ---------------------------------------------------------------------------
# ifnull preservation
# ---------------------------------------------------------------------------
# sqlglot's DuckDB dialect maps IFNULL to exp.Coalesce at parse time, losing
# the original function name.  We mask it with a sentinel before parsing so
# sqlglot treats it as an unknown (Anonymous) function and preserves the name,
# then restore it after generation.

# Sentinel must be the same length as "ifnull" (6 chars) so that AS-column
# alignment computed during generation is not thrown off before the unmask.
_IFNULL_SENTINEL = "_ifnl_"
_IFNULL_RE = re.compile(r"\bifnull\b", re.IGNORECASE)


def _mask_ifnull(sql: str) -> str:
    """Replace ifnull with a sentinel so sqlglot doesn't normalize it to coalesce."""
    return _sub_in_code(_IFNULL_RE, _IFNULL_SENTINEL, sql)


def _unmask_ifnull(sql: str) -> str:
    """Restore ifnull from its sentinel."""
    return sql.replace(_IFNULL_SENTINEL, "ifnull")


# ---------------------------------------------------------------------------
# numeric preservation
# ---------------------------------------------------------------------------
# sqlglot's DuckDB dialect normalises NUMERIC to DType.DECIMAL at parse time,
# losing the original keyword.  We mask it with a same-length sentinel so the
# original spelling is preserved through the format round-trip.
#
# Sentinel is 7 chars (same as "numeric") so type-column alignment in CREATE
# TABLE is not disturbed before the unmask.
_NUMERIC_SENTINEL = "_numer_"
_NUMERIC_RE = re.compile(r"\bnumeric\b", re.IGNORECASE)


def _mask_numeric(sql: str) -> str:
    """Replace numeric with a sentinel so sqlglot doesn't normalise it to decimal."""
    return _sub_in_code(_NUMERIC_RE, _NUMERIC_SENTINEL, sql)


def _unmask_numeric(sql: str) -> str:
    """Restore numeric from its sentinel."""
    return sql.replace(_NUMERIC_SENTINEL, "numeric")


# ---------------------------------------------------------------------------
# Reserved-keyword type-cast pre-processor
# ---------------------------------------------------------------------------
# DuckDB allows user-defined types whose names are SQL reserved words, e.g.
#   COALESCE(x, []::filter[])
# sqlglot fails to parse these because it sees ``filter`` as a keyword token,
# not a type name.  Quoting them - ``::"filter"[]`` - makes sqlglot parse
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
        return f'::"{m.group(1)}"{m.group(2) or ""}'

    return _sub_in_code(_reserved_cast_re(), _replacer, sql)


def _read_dialect(dialect: str) -> type[_DuckDB] | str:
    """Return the parser dialect to use for *dialect*.

    For the DuckDB dialect we substitute our custom subclass that preserves
    bare NUMERIC/DECIMAL types without injecting default precision/scale.
    All other dialects are passed through unchanged.
    """
    return _JARIFY_DIALECT if dialect == DUCKDB_DIALECT else dialect


def parse_sql(sql: str, dialect: str = DUCKDB_DIALECT) -> list[Expression]:
    """Parse a SQL string into a list of sqlglot expression trees.

    Raises ParseError if the SQL is invalid.  Applies a pre-processing step
    to quote DuckDB reserved keywords used as cast type names (e.g.
    ``::filter[]``) so sqlglot can handle them.
    """
    preprocessed = _quote_reserved_cast_types(sql)
    trees = sqlglot.parse(preprocessed, read=_read_dialect(dialect), error_level=sqlglot.ErrorLevel.RAISE)
    return _wrap_nested_joins(_hoist_from_table_joins(trees))


# Set in a query's meta when its joins were moved off a FROM-first query's
# table, so the generator keeps writing it FROM-first.
FROM_FIRST_JOINS_KEY = "jarify_from_first_joins"


def _hoist_from_table_joins(trees: list[Expression]) -> list[Expression]:
    """Move joins that sqlglot attached to a query's FROM table onto the query.

    In a FROM-first query (``FROM t p JOIN d dd ON …``) sqlglot puts the joins
    in the FROM table's ``joins`` arg instead of the query's, where the
    generator renders them. Rendering the table and its alias alone then
    dropped every join. Both placements mean the same query, so the joins are
    moved to the query, ahead of any it already has, and the query is marked
    with ``FROM_FIRST_JOINS_KEY``.
    """
    for tree in trees:
        if tree is None:
            continue
        for select in tree.find_all(_exp.Select):
            from_ = select.args.get("from_")
            table = from_.this if from_ is not None else None
            joins = table.args.get("joins") if isinstance(table, _exp.Table) else None
            if joins:
                table.set("joins", None)
                select.set("joins", [*joins, *(select.args.get("joins") or [])])
                select.meta[FROM_FIRST_JOINS_KEY] = True
    return trees


def _wrap_nested_joins(trees: list[Expression]) -> list[Expression]:
    """Parenthesize a nested join written without parentheses.

    In ``t JOIN u JOIN v ON v.id = u.id ON u.id = t.id`` sqlglot puts
    ``JOIN v`` in the ``joins`` arg of the joined table ``u``, which the
    generator doesn't render, so the join was dropped. The parenthesized form,
    ``t JOIN (u JOIN v ON v.id = u.id) ON u.id = t.id``, means the same and
    parses to the same table wrapped in a subquery node, so it's rewritten to
    that.
    """
    for tree in trees:
        if tree is None:
            continue
        nested = [
            join
            for join in tree.find_all(_exp.Join)
            if isinstance(join.this, _exp.Table) and join.this.args.get("joins")
        ]
        for join in nested:
            join.set("this", _exp.Subquery(this=join.this))
    return trees


def parse_sql_lenient(sql: str, dialect: str = DUCKDB_DIALECT) -> tuple[list[Expression], list[ParseError]]:
    """Parse SQL leniently, collecting errors instead of raising."""
    preprocessed = _quote_reserved_cast_types(sql)
    read = _read_dialect(dialect)
    errors: list[ParseError] = []
    try:
        trees = sqlglot.parse(preprocessed, read=read, error_level=sqlglot.ErrorLevel.RAISE)
    except ParseError:
        # Fall back to lenient parsing so we still get partial trees.
        # Use IGNORE (not WARN) to suppress sqlglot's side-effect stderr prints;
        # errors are re-captured via the RAISE pass below.
        trees = sqlglot.parse(preprocessed, read=read, error_level=sqlglot.ErrorLevel.IGNORE)
        # Re-parse to capture the actual errors
        try:
            sqlglot.parse(preprocessed, read=read, error_level=sqlglot.ErrorLevel.RAISE)
        except ParseError as e:
            errors.append(e)
    return _wrap_nested_joins(_hoist_from_table_joins(trees)), errors
