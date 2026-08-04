"""Conversion logic, free of CLI concerns so it stays usable as a library."""

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence

from PIL import Image, ImageOps

DEFAULT_INCLUDE = ("jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp")
DEFAULT_FORMAT = "tiff"
DEFAULT_QUALITY = 85

#: Formats that cannot store an alpha channel. Images are flattened to RGB
#: before saving to one of these, otherwise Pillow raises OSError.
NO_ALPHA_FORMATS = frozenset({"JPEG", "BMP"})

#: Formats where ``quality`` is meaningful. Passing it elsewhere is harmless
#: but pointless, so it is dropped.
QUALITY_FORMATS = frozenset({"JPEG", "WEBP"})

#: Extension to write for formats whose canonical suffix differs from the
#: format name the user types.
_EXTENSION_ALIASES = {"jpeg": "jpg"}

#: User-facing format name to the Pillow format identifier.
_PILLOW_FORMAT_ALIASES = {"jpg": "JPEG", "tif": "TIFF"}


class Status(str, Enum):
    CONVERTED = "converted"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class Options:
    """Everything a worker needs to convert one file. Must stay picklable."""

    target_format: str = DEFAULT_FORMAT
    quality: int = DEFAULT_QUALITY
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    overwrite: bool = False

    @property
    def pillow_format(self) -> str:
        fmt = self.target_format.lower()
        return _PILLOW_FORMAT_ALIASES.get(fmt, fmt.upper())


@dataclass(frozen=True)
class Result:
    src: Path
    dst: Path
    status: Status
    error: Optional[str] = None


@dataclass
class Summary:
    results: List[Result] = field(default_factory=list)

    def add(self, result: Result) -> None:
        self.results.append(result)

    def _count(self, status: Status) -> int:
        return sum(1 for r in self.results if r.status is status)

    @property
    def converted(self) -> int:
        return self._count(Status.CONVERTED)

    @property
    def skipped(self) -> int:
        return self._count(Status.SKIPPED)

    @property
    def failed(self) -> int:
        return self._count(Status.FAILED)

    @property
    def failures(self) -> List[Result]:
        return [r for r in self.results if r.status is Status.FAILED]


def normalize_extensions(extensions: Iterable[str]) -> frozenset:
    """Accept ``jpg``, ``.jpg`` or ``.JPG`` and return ``{'.jpg'}``."""
    return frozenset(
        f".{ext.lower().lstrip('.')}" for ext in extensions if ext.strip()
    )


def target_extension(target_format: str) -> str:
    fmt = target_format.lower().lstrip(".")
    return _EXTENSION_ALIASES.get(fmt, fmt)


def discover(
    source: Path,
    include: Iterable[str] = DEFAULT_INCLUDE,
    recursive: bool = False,
) -> Iterator[Path]:
    """Yield image files under ``source`` whose extension is in ``include``.

    Matching is case-insensitive, so ``.jpg`` also picks up ``.JPG``.
    """
    wanted = normalize_extensions(include)
    walk = source.rglob("*") if recursive else source.iterdir()

    for path in sorted(walk):
        if path.is_file() and path.suffix.lower() in wanted:
            yield path


def plan_output(src: Path, source_root: Path, out_dir: Path, target_format: str) -> Path:
    """Compute the destination path, mirroring ``src``'s position under root.

    Uses :attr:`Path.stem`, so names carrying more than one dot survive intact.
    """
    relative = src.relative_to(source_root).parent
    name = f"{src.stem.lower()}.{target_extension(target_format)}"

    return out_dir / relative / name


def needs_conversion(src: Path, dst: Path, overwrite: bool) -> bool:
    """False when ``dst`` already exists and is no older than ``src``."""
    if overwrite or not dst.exists():
        return True

    return src.stat().st_mtime > dst.stat().st_mtime


def _save_kwargs(pillow_format: str, options: Options) -> dict:
    if pillow_format in QUALITY_FORMATS:
        return {"quality": options.quality}

    return {}


def convert_one(src: Path, dst: Path, options: Options) -> Result:
    """Convert a single file. Never raises: failures come back as a Result."""
    try:
        if not needs_conversion(src, dst, options.overwrite):
            return Result(src, dst, Status.SKIPPED)

        pillow_format = options.pillow_format

        with Image.open(src) as img:
            # Honour the EXIF orientation tag so phone photos aren't rotated.
            img = ImageOps.exif_transpose(img)

            if options.max_width or options.max_height:
                img.thumbnail(
                    (options.max_width or img.width, options.max_height or img.height),
                    Image.LANCZOS,
                )

            if pillow_format in NO_ALPHA_FORMATS and img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            dst.parent.mkdir(parents=True, exist_ok=True)
            img.save(dst, format=pillow_format, **_save_kwargs(pillow_format, options))

        return Result(src, dst, Status.CONVERTED)
    except Exception as exc:  # noqa: BLE001 - one bad file must not kill the batch
        return Result(src, dst, Status.FAILED, f"{type(exc).__name__}: {exc}")


def _job(args) -> Result:
    """Module-level trampoline so the payload is picklable for the pool."""
    return convert_one(*args)


def run(
    files: Sequence[Path],
    source_root: Path,
    out_dir: Path,
    options: Options,
    jobs: Optional[int] = None,
) -> Iterator[Result]:
    """Convert ``files``, yielding each Result as it completes.

    ``jobs=1`` runs in-process, which keeps tracebacks and profiling readable.
    """
    payloads = [
        (src, plan_output(src, source_root, out_dir, options.target_format), options)
        for src in files
    ]

    workers = jobs or os.cpu_count() or 1

    if workers == 1:
        for payload in payloads:
            yield _job(payload)
        return

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_job, payload) for payload in payloads]
        for future in as_completed(futures):
            yield future.result()
