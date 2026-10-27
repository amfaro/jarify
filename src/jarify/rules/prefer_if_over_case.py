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


def _has_comments(node: exp.Case) -> bool:
    """Return True if a comment is attached to *node* or sits inside its branches.

    IF() renders its arguments on one line, where a ``--`` comment would
    swallow the rest of the call, so commented branches stay as CASE.  A
    comment attached to the CASE itself, such as one on the line above a
    CASE nested in another CASE's ELSE, keeps the CASE too: sqlglot drops a
    comment attached to an ``if()`` call when it parses the call.
    """
    return any(n.comments for n in node.walk())


def _is_rewritable(node: exp.Case) -> bool:
    """Return True when *node* should be rewritten to IF()."""
    return not _is_simple_case(node) and _is_single_when(node) and not _has_comments(node)


class PreferIfOverCaseRule(FormatterRule):
    """Format and lint: rewrite single-branch CASE WHEN … THEN … [ELSE …] END to IF().

    DuckDB supports ``IF(condition, true_val, false_val)`` as a first-class
    function.  For searched CASE expressions with exactly one WHEN branch the
    IF form is shorter and more idiomatic.

    **Scope**:

    - Applies only to *searched* CASE (``CASE WHEN cond THEN val …``).
    - Simple CASE (``CASE expr WHEN lit …``) is left unchanged.
    - CASE with 2+ WHEN branches is left unchanged.
    - CASE carrying a comment, on itself or inside a branch, is left unchanged.
    - A CASE nested in another CASE's branch is rewritten in the same pass.

    **ELSE handling**: When the CASE has no ELSE clause the implicit return
    value is ``NULL``.  The rewrite always emits the third argument explicitly
    (``IF(cond, val, NULL)``) because DuckDB's ``IF()`` function requires
    exactly three arguments — a two-argument call raises
    ``Parser Error: Wrong number of arguments to IF``.

    **Format**: The ``apply()`` method rewrites matching ``exp.Case`` nodes to
    ``exp.If`` in-place.  The ``JarifyGenerator.if_sql()`` override then renders
    ``exp.If`` as ``IF(cond, then, else)`` instead of the default CASE WHEN form.

    **Lint**: The ``check()`` method flags any ``exp.Case`` node that matches the
    rewrite criteria but has not yet been formatted.
    """

    def __init__(self, severity: str = "warn", overrides=None) -> None:
        super().__init__(overrides=overrides)
        self.severity = severity

    @property
    def name(self) -> str:
        return "prefer-if-over-case"

    def _rewritable_cases(self, tree: exp.Expression) -> list[exp.Case]:
        """Return the CASE nodes to rewrite, each before any CASE nested in it.

        ``apply()`` and ``check()`` both use this list, so ``check()`` reports
        exactly the CASE nodes that ``apply()`` rewrites.
        """
        return [case for case in tree.find_all(exp.Case) if _is_rewritable(case) and self.enabled_for_node(case)]

    def apply(self, tree: exp.Expression) -> exp.Expression:
        """Rewrite matching CASE nodes to exp.If in-place."""
        # Rewrite innermost first. A CASE nested in the branch of another one
        # is then already an IF() when its parent's branches move into the
        # parent's IF(), so one pass rewrites every level of nesting.
        for case in reversed(self._rewritable_cases(tree)):
            if_branch = case.args["ifs"][0]
            # Use the explicit ELSE value, or NULL to satisfy DuckDB's
            # requirement that IF() always takes exactly three arguments.
            else_val = case.args.get("default")
            replacement = exp.If(
                this=if_branch.args["this"],
                true=if_branch.args["true"],
                false=else_val if else_val is not None else exp.Null(),
            )
            case.replace(replacement)

        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []
        for case in self._rewritable_cases(tree):
            _line, _col = _node_pos(case)
            violations.append(
                LintViolation(
                    rule=self.name,
                    severity=self.severity,
                    message=("Single-branch CASE WHEN … THEN … END can be rewritten as IF(cond, then, else)"),
                    line=_line,
                    column=_col,
                )
            )
        return violations
