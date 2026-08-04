# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Parallel batch image converter, installed as an `imgconvert` console script. Reads a source
directory, converts matching images into a target directory, and never touches the source.

## Commands

Dependencies are managed with **uv**. Never call `pip` or a bare `pytest`/`flake8` here —
there is no activated venv, and `uv run` is what resolves the environment.

```bash
make sync      # uv sync — create/update .venv from uv.lock
make check     # lint + tests
make test      # uv run pytest
make lint      # uv run flake8 .
make build     # uv build -> dist/
make upgrade   # uv lock --upgrade
make help      # list documented targets (default goal)
```

Run the CLI: `uv run imgconvert <args>` (or `make run ARGS="..."`).

Run a single test:
`uv run pytest tests/test_core.py::TestDiscover::test_matches_case_insensitively`

`uv.lock` and `.python-version` (3.14) are committed on purpose — they pin the whole
environment including the interpreter. Adding a dependency means `uv add <pkg>`
(or `uv add --dev <pkg>`), which updates both `pyproject.toml` and the lock; don't
hand-edit dependency lists.

## Architecture

`src/` layout, packaged with hatchling. Two modules, split so the logic stays importable as
a library (the README documents that use):

- **`core.py`** — all conversion logic, no CLI concerns.
  - `discover()` — one pass yielding matching files. Replaces the old read-then-filter
    two-step. Extension matching is case-insensitive.
  - `plan_output()` — destination path, mirroring relative structure under `--recursive`.
  - `convert_one()` — **must never raise.** Returns a `Result` with status
    `converted | skipped | failed`. This is what keeps one corrupt file from killing a batch.
  - `run()` — drives a `ProcessPoolExecutor`, yields `Result`s via `as_completed`.
- **`cli.py`** — Typer app, progress bar, summary rendering, exit code.

### Parallelism

`jobs=1` deliberately takes an in-process path rather than a one-worker pool — it keeps
tracebacks and profiling readable. Everything submitted to the pool must be picklable, hence
the module-level `_job` trampoline and the frozen `Options` dataclass; don't pass `Image`
objects across the process boundary.

Measured on 16 cores: ~6.8x on 12MP photos (5.5s → 0.8s for 60 files), ~3.9x on small
800x600 images where pool startup dominates. Serial and parallel output are byte-identical.

## Image handling gotchas

These are all encoded in `convert_one()` and covered by tests — don't regress them:

- **Alpha.** Saving RGBA as JPEG raises `OSError`. Formats in `NO_ALPHA_FORMATS` get an
  `img.convert("RGB")` first.
- **EXIF orientation.** `ImageOps.exif_transpose()` runs before save, or phone photos come
  out rotated.
- **Quality** is only meaningful for JPEG/WebP (`QUALITY_FORMATS`); it's dropped elsewhere
  rather than passed through and erroring.
- **Multi-dot filenames.** Use `Path.stem`, never `name.split('.')` — `my.photo.v2.jpeg` must
  survive. The pre-rewrite code crashed on these.
- **Output directories** are created by `convert_one()`, not by the Makefile.

## Notes

- There is no config file. The CLI is flags-only by design — the old `config.yml` carried a
  `<source_dir>` placeholder that had to be hand-edited before every run.
- Dependencies use floors (`pillow>=11`) in `pyproject.toml`, with exact versions pinned in
  `uv.lock`. The previous `Pillow==9.0.1` pin in `requirements.txt` could not build on
  modern Python — that failure mode is what the floors-plus-lockfile split avoids.
- Dev tooling lives in a PEP 735 `[dependency-groups]` block, not
  `[project.optional-dependencies]`, so it stays out of the published wheel.
