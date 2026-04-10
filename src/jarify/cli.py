"""Command-line interface for jarify."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from jarify.config import load_config
from jarify.formatter import format_sql
from jarify.linter import lint_sql

console = Console(stderr=True)


@click.group()
@click.version_option(package_name="jarify")
def main() -> None:
    """jarify — bespoke SQL linter & formatter for DuckDB."""


@main.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--check", is_flag=True, help="Check formatting without writing changes.")
def fmt(files: tuple[Path, ...], config_path: Path | None, check: bool) -> None:
    """Format SQL files."""
    config = load_config(config_path)
    any_changed = False

    for file_path in _collect_sql_files(files):
        original = file_path.read_text()
        formatted = format_sql(original, config)
        if original != formatted:
            any_changed = True
            if check:
                console.print(f"[yellow]would reformat[/] {file_path}")
            else:
                file_path.write_text(formatted)
                console.print(f"[green]reformatted[/] {file_path}")
        else:
            console.print(f"[dim]unchanged[/] {file_path}")

    if check and any_changed:
        raise SystemExit(1)


@main.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
def lint(files: tuple[Path, ...], config_path: Path | None) -> None:
    """Lint SQL files and report violations."""
    config = load_config(config_path)
    total_violations = 0

    for file_path in _collect_sql_files(files):
        violations = lint_sql(file_path.read_text(), config)
        for v in violations:
            console.print(f"[red]{file_path}[/]{v}")
        total_violations += len(violations)

    if total_violations:
        console.print(f"\n[bold red]{total_violations} violation(s) found[/]")
        raise SystemExit(1)
    else:
        console.print("[bold green]All clean![/]")


def _collect_sql_files(paths: tuple[Path, ...]) -> list[Path]:
    """Expand directories into .sql files, pass files through directly."""
    sql_files: list[Path] = []
    for p in paths:
        if p.is_dir():
            sql_files.extend(sorted(p.rglob("*.sql")))
        elif p.suffix == ".sql":
            sql_files.append(p)
    return sql_files
