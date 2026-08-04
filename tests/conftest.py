from pathlib import Path

import pytest
from PIL import Image


def make_image(path: Path, mode: str = "RGB", size=(16, 16)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, (120, 60, 30) if mode == "RGB" else None).save(path)

    return path


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A source tree covering the cases that used to break the old code."""
    src = tmp_path / "src"

    make_image(src / "plain.jpg")
    make_image(src / "UPPER.PNG")
    make_image(src / "my.photo.v2.jpeg")          # multi-dot name
    make_image(src / "nested" / "deep.png")       # only seen with --recursive
    Image.new("RGBA", (16, 16), (1, 2, 3, 4)).save(src / "alpha.png")

    # Non-images that must be ignored, adjacent so a buggy filter reveals itself.
    (src / "notes.txt").write_text("not an image")
    (src / "notes2.txt").write_text("not an image")
    (src / "notes3.txt").write_text("not an image")

    # Truncated JPEG to exercise the failure path.
    (src / "broken.jpg").write_bytes(b"\xff\xd8\xff\xe0 not really a jpeg")

    return src
