"""Command line entry point."""

import os
from pathlib import Path
from typing import List, Optional

import typer
from tqdm import tqdm

from imgconvert.core import (
    DEFAULT_FORMAT,
    DEFAULT_INCLUDE,
    DEFAULT_QUALITY,
    Options,
    Summary,
    discover,
    plan_output,
    run,
)

app = typer.Typer(
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Convert a directory of images to another format, in parallel.\n\n"
    "Source files are only ever read, never modified.",
)


def _cpu_default() -> int:
    return os.cpu_count() or 1


@app.command()
def convert(
    source: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Directory to read images from.",
    ),
    out: Path = typer.Option(
        Path("converted"), "-o", "--out", help="Directory to write converted images to."
    ),
    target_format: str = typer.Option(
        DEFAULT_FORMAT, "-f", "--format", help="Target image format."
    ),
    jobs: int = typer.Option(
        None,
        "-j",
        "--jobs",
        min=1,
        show_default="one per CPU",
        help="Parallel workers.",
    ),
    recursive: bool = typer.Option(
        False, "-r", "--recursive", help="Walk subdirectories, mirroring the tree in --out."
    ),
    include: Optional[List[str]] = typer.Option(
        None,
        "--include",
        show_default=" ".join(DEFAULT_INCLUDE),
        help="Input extensions, repeatable.",
    ),
    max_width: Optional[int] = typer.Option(
        None, "--max-width", min=1, help="Downscale to fit this width, preserving aspect."
    ),
    max_height: Optional[int] = typer.Option(
        None, "--max-height", min=1, help="Downscale to fit this height, preserving aspect."
    ),
    quality: int = typer.Option(
        DEFAULT_QUALITY, "--quality", min=1, max=100, help="JPEG/WebP quality."
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Reconvert files that already exist in --out."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="List what would be converted, write nothing."
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Name every file handled."),
) -> None:
    workers = jobs or _cpu_default()
    extensions = include or list(DEFAULT_INCLUDE)

    options = Options(
        target_format=target_format,
        quality=quality,
        max_width=max_width,
        max_height=max_height,
        overwrite=overwrite,
    )

    files = list(discover(source, extensions, recursive))

    if not files:
        typer.echo(f"No matching images found in {source}.")
        raise typer.Exit(0)

    if dry_run:
        for src in files:
            dst = plan_output(src, source, out, target_format)
            typer.echo(f"{src} -> {dst}")
        typer.echo(f"\n{len(files)} files would be converted to {out}.")
        raise typer.Exit(0)

    summary = Summary()
    progress = tqdm(
        run(files, source, out, options, workers),
        total=len(files),
        desc=f"Converting to {target_format}",
        unit="img",
    )

    for result in progress:
        summary.add(result)
        if verbose:
            progress.write(f"{result.status.value:<9} {result.src.name}")

    _report(summary, out)

    if summary.failed:
        raise typer.Exit(1)


def _report(summary: Summary, out: Path) -> None:
    typer.echo(
        f"\n{summary.converted:,} converted"
        f" · {summary.skipped:,} skipped"
        f" · {summary.failed:,} failed"
        f"  ->  {out}"
    )

    for result in summary.failures:
        typer.echo(f"  FAILED  {result.src}: {result.error}", err=True)


if __name__ == "__main__":
    app()
