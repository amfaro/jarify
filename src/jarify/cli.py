"""Command-line interface for jarify."""

from __future__ import annotations

import dataclasses
import difflib
import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.syntax import Syntax

from jarify.config import load_config
from jarify.formatter import format_sql
from jarify.linter import lint_sql

console = Console(stderr=True, no_color=bool(os.environ.get("NO_COLOR")))

_STARTER_CONFIG = """\
# jarify.toml — SQL linter & formatter configuration
# https://github.com/your-org/jarify

[jarify]
dialect         = "duckdb"
indent          = 2
max_line_length = 120

# Comma placement: set trailing_commas = false and leading_commas = true
# to use leading commas (SQL Server / dbt style)
trailing_commas = true
leading_commas  = false

# Normalize bare JOIN → INNER JOIN
normalize_join = true

# Lint rule severity: "off" | "warn" | "error"
no_select_star         = "warn"
no_unused_cte          = "warn"
no_implicit_cross_join = "warn"
duckdb_type_style      = "warn"
duckdb_prefer_qualify  = "warn"
"""


@click.group()
@click.version_option(package_name="jarify")
def main() -> None:
    """jarify — bespoke SQL linter & formatter for DuckDB."""


@main.command("fmt")
@click.argument("files", nargs=-1, type=click.Path(path_type=Path))
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--check", is_flag=True, help="Exit non-zero if any file would change; don't write.")
@click.option("--diff", is_flag=True, help="Print a unified diff of changes instead of writing.")
@click.option("--stdin-filename", default="<stdin>", help="Filename label when reading from stdin.")
def fmt(
    files: tuple[Path, ...],
    config_path: Path | None,
    check: bool,
    diff: bool,
    stdin_filename: str,
) -> None:
    """Format SQL files in-place (or check/diff without writing).

    Pass - as a file argument to read from stdin.
    """
    config_start = Path(stdin_filename).parent if stdin_filename != "<stdin>" else None
    config = load_config(config_path, start=config_start)
    any_changed = False

    inputs = _resolve_inputs(files, stdin_filename)
    if not inputs:
        console.print("[yellow]No SQL files found.[/]")
        return

    for label, original, target_path in inputs:
        try:
            formatted, warnings = format_sql(original, config)
        except Exception as exc:
            console.print(f"[red]ERROR[/] {label}: {exc}")
            sys.exit(2)

        for w in warnings:
            console.print(f"[yellow]WARN[/] {label}: {w}")
            any_changed = any_changed  # parse warnings → don't count as reformatted

        if original == formatted:
            if not diff:
                console.print(f"[dim]unchanged[/] {label}")
            continue

        any_changed = True

        if diff:
            _print_diff(label, original, formatted)
        elif check:
            console.print(f"[yellow]would reformat[/] {label}")
        elif target_path is None:
            # stdin — write formatted SQL to stdout
            click.echo(formatted, nl=False)
        else:
            target_path.write_text(formatted)
            console.print(f"[green]reformatted[/] {label}")

    if check and any_changed:
        sys.exit(1)


@main.command("lint")
@click.argument("files", nargs=-1, type=click.Path(path_type=Path))
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--stdin-filename", default="<stdin>", help="Filename label when reading from stdin.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format: text (default) or json.",
)
def lint(
    files: tuple[Path, ...],
    config_path: Path | None,
    stdin_filename: str,
    output_format: str,
) -> None:
    """Lint SQL files and report violations.

    Exit code: 0 = clean, 1 = violations found, 2 = error.
    Pass - as a file argument to read from stdin.
    """
    config_start = Path(stdin_filename).parent if stdin_filename != "<stdin>" else None
    config = load_config(config_path, start=config_start)
    total_violations = 0
    has_errors = False
    all_results: list[tuple[str, list]] = []

    inputs = _resolve_inputs(files, stdin_filename)
    if not inputs:
        if output_format == "json":
            click.echo("[]")
        else:
            console.print("[yellow]No SQL files found.[/]")
        return

    for label, sql, _ in inputs:
        try:
            violations = lint_sql(sql, config)
        except Exception as exc:
            if output_format == "json":
                err = {
                    "filename": label,
                    "line": None,
                    "column": None,
                    "severity": "error",
                    "rule": "internal-error",
                    "message": str(exc),
                }
                click.echo(json.dumps([err]))
            else:
                console.print(f"[red]ERROR[/] {label}: {exc}")
            sys.exit(2)

        all_results.append((label, violations))
        for v in violations:
            if v.severity == "error":
                has_errors = True
        total_violations += len(violations)

    if output_format == "json":
        output = [v.to_dict(label) for label, violations in all_results for v in violations]
        click.echo(json.dumps(output))
    else:
        for label, violations in all_results:
            for v in violations:
                color = "red" if v.severity == "error" else "yellow"
                console.print(f"[{color}]{label}[/{color}]{v}")

        if total_violations:
            color = "red" if has_errors else "yellow"
            console.print(f"\n[bold {color}]{total_violations} violation(s) found[/]")
        else:
            console.print("[bold green]All clean![/]")

    if total_violations:
        sys.exit(1)


@main.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing jarify.toml.")
def init(force: bool) -> None:
    """Create a starter jarify.toml in the current directory."""
    target = Path.cwd() / "jarify.toml"
    if target.exists() and not force:
        console.print(f"[yellow]{target} already exists.[/] Use --force to overwrite.")
        sys.exit(1)
    target.write_text(_STARTER_CONFIG)
    console.print(f"[green]Created[/] {target}")


@main.command("show-config")
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
def show_config(config_path: Path | None) -> None:
    """Display the resolved configuration as TOML."""
    config = load_config(config_path)
    lines = ["[jarify]"]
    for f in dataclasses.fields(config):
        if f.name == "rules":
            continue
        val = getattr(config, f.name)
        if isinstance(val, bool):
            lines.append(f"{f.name:<22} = {'true' if val else 'false'}")
        elif isinstance(val, str):
            lines.append(f'{f.name:<22} = "{val}"')
        else:
            lines.append(f"{f.name:<22} = {val}")
    toml_text = "\n".join(lines) + "\n"
    console.print(Syntax(toml_text, "toml", theme="monokai"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_inputs(
    paths: tuple[Path, ...],
    stdin_label: str,
) -> list[tuple[str, str, Path | None]]:
    """Return (label, content, output_path_or_None) for each input.

    - stdin is signaled by a path of exactly `-`
    - directories are expanded to all *.sql files within
    - non-.sql files are skipped with a warning
    """
    results: list[tuple[str, str, Path | None]] = []

    if not paths:
        return results

    for p in paths:
        if str(p) == "-":
            results.append((stdin_label, sys.stdin.read(), None))
            continue
        if p.is_dir():
            for sql_file in sorted(p.rglob("*.sql")):
                results.append((str(sql_file), sql_file.read_text(), sql_file))
        elif p.suffix == ".sql":
            if not p.exists():
                console.print(f"[red]ERROR[/] File not found: {p}")
                sys.exit(2)
            results.append((str(p), p.read_text(), p))
        else:
            console.print(f"[dim]skipping non-.sql file:[/] {p}")

    return results


def _print_diff(label: str, original: str, formatted: str) -> None:
    original_lines = original.splitlines(keepends=True)
    formatted_lines = formatted.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            original_lines,
            formatted_lines,
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
        )
    )
    if diff_lines:
        diff_text = "".join(diff_lines)
        if console.is_terminal and not console.no_color:
            console.print(Syntax(diff_text, "diff", theme="monokai"))
        else:
            click.echo(diff_text, err=True)
