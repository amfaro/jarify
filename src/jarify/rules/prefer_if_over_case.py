"""Rule: rewrite single-WHEN searched CASE expressions to IF()."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule, _node_pos
from jarify.types import LintViolation


def _is_simple_case(node: exp.Case) -> bool:
    """Return True if *node* is a simple CASE (has a subject expression).

    Simple form: ``CASE expr WHEN lit THEN val … END``
    This form cannot be trivially rewritten to IF() and is excluded.
    """
    return node.args.get("this") is not None


def _is_single_when(node: exp.Case) -> bool:
    """Return True if *node* has exactly one WHEN branch."""
    return len(node.args.get("ifs", [])) == 1


def _is_rewritable(node: exp.Case) -> bool:
    """Return True when *node* should be rewritten to IF()."""
    return not _is_simple_case(node) and _is_single_when(node)


class PreferIfOverCaseRule(FormatterRule):
    """Format and lint: rewrite single-branch CASE WHEN … THEN … [ELSE …] END to IF().

    DuckDB supports ``IF(condition, true_val[, false_val])`` as a first-class
    function.  For searched CASE expressions with exactly one WHEN branch the
    IF form is shorter and more idiomatic.

    **Scope**:

    - Applies only to *searched* CASE (``CASE WHEN cond THEN val …``).
    - Simple CASE (``CASE expr WHEN lit …``) is left unchanged.
    - CASE with 2+ WHEN branches is left unchanged.

    **Format**: The ``apply()`` method rewrites matching ``exp.Case`` nodes to
    ``exp.If`` in-place.  The ``JarifyGenerator.if_sql()`` override then renders
    ``exp.If`` as ``IF(cond, then[, else])`` instead of the default CASE WHEN form.

    **Lint**: The ``check()`` method flags any ``exp.Case`` node that matches the
    rewrite criteria but has not yet been formatted.
    """

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "prefer-if-over-case"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        """Rewrite matching CASE nodes to exp.If in-place."""
        for case in tree.find_all(exp.Case):
            if not _is_rewritable(case):
                continue
            if_branch = case.args["ifs"][0]
            condition = if_branch.args["this"]
            then_val = if_branch.args["true"]
            else_val = case.args.get("default")  # None when there is no ELSE

            replacement = exp.If(
                this=condition.copy(),
                true=then_val.copy(),
                **({"false": else_val.copy()} if else_val is not None else {}),
            )
            case.replace(replacement)

        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []
        for case in tree.find_all(exp.Case):
            if not _is_rewritable(case):
                continue
            _line, _col = _node_pos(case)
            violations.append(
                LintViolation(
                    rule=self.name,
                    severity=self.severity,
                    message=("Single-branch CASE WHEN … THEN … END can be rewritten as IF(cond, then[, else])"),
                    line=_line,
                    column=_col,
                )
            )
        return violations
