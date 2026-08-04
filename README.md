# imgconvert

Convert a directory of images to another format, in parallel.

Source files are only ever read — never modified, moved, or deleted.

## Install

The project is managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync               # creates .venv from uv.lock, exactly as pinned
uv run imgconvert --help
```

To install it as a standalone tool on your PATH, no venv juggling:

```bash
uv tool install .
imgconvert --help
```

Or run it once without installing anything:

```bash
uvx --from . imgconvert ~/Pictures/raw
```

## Usage

```bash
imgconvert ~/Pictures/raw                              # -> ./converted/*.tiff
imgconvert ~/Pictures/raw -o out -f webp               # WebP into ./out
imgconvert ~/Pictures/raw -r --max-width 1920          # recurse + downscale
imgconvert ~/Pictures/raw -f jpeg --quality 90
imgconvert ~/Pictures/raw --dry-run                    # show the plan, write nothing
```

Prefix with `uv run` if you synced instead of installing as a tool.

| Flag | Default | |
|---|---|---|
| `SOURCE` | — | directory to read (required) |
| `-o, --out` | `converted` | output directory, created if missing |
| `-f, --format` | `tiff` | target format |
| `-j, --jobs` | one per CPU | parallel workers; `-j 1` runs in-process |
| `-r, --recursive` | off | walk subdirectories, mirroring the tree into `--out` |
| `--include` | `jpg jpeg png bmp tiff tif webp` | input extensions, repeatable |
| `--max-width` / `--max-height` | — | downscale to fit, preserving aspect ratio |
| `--quality` | `85` | JPEG/WebP only; ignored for other formats |
| `--overwrite` | off | reconvert files already present in `--out` |
| `--dry-run` | off | list what would be converted |
| `-v, --verbose` | off | name every file handled |

Extension matching is case-insensitive, so `--include jpg` also picks up `.JPG`.

### Behaviour worth knowing

- **Re-runs are cheap.** Files already present in `--out` and newer than their source are
  skipped, so an interrupted run resumes where it left off. Use `--overwrite` to force.
- **One bad file doesn't stop the batch.** Failures are collected and reported at the end;
  the exit code is `1` if anything failed.
- **EXIF orientation is applied**, so phone photos don't come out sideways.
- **Alpha is flattened** when the target format can't store it (e.g. PNG → JPEG).

## Library use

```python
from pathlib import Path
from imgconvert import Options, Status, discover, run

src = Path("~/Pictures/raw").expanduser()
files = list(discover(src, ["jpg", "png"], recursive=True))

for result in run(files, src, Path("converted"), Options(target_format="tiff"), jobs=8):
    if result.status is Status.FAILED:
        print(result.src, result.error)
```

## Development

```bash
make sync     # uv sync
make check    # lint + tests
make test     # uv run pytest
make lint     # uv run flake8
make build    # uv build -> dist/
make upgrade  # uv lock --upgrade
make help     # list all targets
```

`uv.lock` and `.python-version` are committed deliberately, so `uv sync` reproduces the
same environment (down to the Python interpreter) on any machine.
