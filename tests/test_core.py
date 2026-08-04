from pathlib import Path

from PIL import Image

from imgconvert.core import (
    Options,
    Status,
    convert_one,
    discover,
    needs_conversion,
    normalize_extensions,
    plan_output,
    run,
    target_extension,
)


class TestDiscover:
    def test_filters_to_requested_extensions(self, corpus: Path):
        found = {p.name for p in discover(corpus, ["jpg", "jpeg", "png"])}

        assert "notes.txt" not in found
        # Three .txt files sit next to each other; the old pop-while-iterating
        # filter let every second one through.
        assert not any(n.endswith(".txt") for n in found)

    def test_matches_case_insensitively(self, corpus: Path):
        found = {p.name for p in discover(corpus, ["png"])}

        assert "UPPER.PNG" in found

    def test_non_recursive_skips_subdirectories(self, corpus: Path):
        found = {p.name for p in discover(corpus, ["png"], recursive=False)}

        assert "deep.png" not in found

    def test_recursive_includes_subdirectories(self, corpus: Path):
        found = {p.name for p in discover(corpus, ["png"], recursive=True)}

        assert "deep.png" in found

    def test_accepts_extensions_with_or_without_dot(self, corpus: Path):
        assert {p.name for p in discover(corpus, [".JPG"])} == {
            p.name for p in discover(corpus, ["jpg"])
        }


class TestNormalizeExtensions:
    def test_normalizes_case_and_leading_dot(self):
        assert normalize_extensions(["JPG", ".jpeg", "png"]) == {".jpg", ".jpeg", ".png"}

    def test_drops_blanks(self):
        assert normalize_extensions(["jpg", "", "  "]) == {".jpg"}


class TestPlanOutput:
    def test_preserves_multi_dot_stems(self, tmp_path: Path):
        src = tmp_path / "my.photo.v2.jpeg"
        dst = plan_output(src, tmp_path, tmp_path / "out", "tiff")

        assert dst.name == "my.photo.v2.tiff"

    def test_lowercases_the_stem(self, tmp_path: Path):
        dst = plan_output(tmp_path / "UPPER.PNG", tmp_path, tmp_path / "out", "tiff")

        assert dst.name == "upper.tiff"

    def test_mirrors_nested_structure(self, tmp_path: Path):
        src = tmp_path / "a" / "b" / "deep.png"
        dst = plan_output(src, tmp_path, tmp_path / "out", "tiff")

        assert dst == tmp_path / "out" / "a" / "b" / "deep.tiff"

    def test_jpeg_target_writes_jpg_extension(self, tmp_path: Path):
        dst = plan_output(tmp_path / "x.png", tmp_path, tmp_path / "out", "jpeg")

        assert dst.name == "x.jpg"


class TestTargetExtension:
    def test_aliases_jpeg_to_jpg(self):
        assert target_extension("jpeg") == "jpg"

    def test_passes_through_others(self):
        assert target_extension("tiff") == "tiff"


class TestConvertOne:
    def test_writes_the_target_format(self, corpus: Path, tmp_path: Path):
        dst = tmp_path / "out" / "plain.tiff"
        result = convert_one(corpus / "plain.jpg", dst, Options(target_format="tiff"))

        assert result.status is Status.CONVERTED
        with Image.open(dst) as img:
            assert img.format == "TIFF"

    def test_creates_missing_output_directory(self, corpus: Path, tmp_path: Path):
        dst = tmp_path / "deeply" / "nested" / "out" / "plain.tiff"
        result = convert_one(corpus / "plain.jpg", dst, Options())

        assert result.status is Status.CONVERTED
        assert dst.exists()

    def test_reports_failure_instead_of_raising(self, corpus: Path, tmp_path: Path):
        result = convert_one(corpus / "broken.jpg", tmp_path / "broken.tiff", Options())

        assert result.status is Status.FAILED
        assert result.error

    def test_flattens_alpha_for_jpeg(self, corpus: Path, tmp_path: Path):
        dst = tmp_path / "alpha.jpg"
        result = convert_one(corpus / "alpha.png", dst, Options(target_format="jpeg"))

        assert result.status is Status.CONVERTED
        with Image.open(dst) as img:
            assert img.mode == "RGB"

    def test_leaves_the_source_untouched(self, corpus: Path, tmp_path: Path):
        src = corpus / "plain.jpg"
        before = src.read_bytes()

        convert_one(src, tmp_path / "plain.tiff", Options())

        assert src.read_bytes() == before

    def test_downscales_to_max_width(self, tmp_path: Path):
        src = tmp_path / "big.png"
        Image.new("RGB", (400, 200)).save(src)
        dst = tmp_path / "big.tiff"

        convert_one(src, dst, Options(max_width=100))

        with Image.open(dst) as img:
            assert img.size == (100, 50)

    def test_skips_when_output_is_current(self, corpus: Path, tmp_path: Path):
        src, dst = corpus / "plain.jpg", tmp_path / "plain.tiff"

        assert convert_one(src, dst, Options()).status is Status.CONVERTED
        assert convert_one(src, dst, Options()).status is Status.SKIPPED

    def test_overwrite_forces_reconversion(self, corpus: Path, tmp_path: Path):
        src, dst = corpus / "plain.jpg", tmp_path / "plain.tiff"

        convert_one(src, dst, Options())
        result = convert_one(src, dst, Options(overwrite=True))

        assert result.status is Status.CONVERTED


class TestNeedsConversion:
    def test_true_when_target_missing(self, tmp_path: Path):
        assert needs_conversion(tmp_path / "a.jpg", tmp_path / "missing.tiff", False)

    def test_true_when_source_is_newer(self, tmp_path: Path):
        src, dst = tmp_path / "a.jpg", tmp_path / "a.tiff"
        dst.write_bytes(b"")
        src.write_bytes(b"")
        import os

        os.utime(dst, (1, 1))

        assert needs_conversion(src, dst, False)


class TestRun:
    def test_serial_and_parallel_agree(self, corpus: Path, tmp_path: Path):
        files = list(discover(corpus, ["jpg", "jpeg", "png"], recursive=True))
        options = Options(target_format="tiff")

        serial = {
            r.dst.name: r.status
            for r in run(files, corpus, tmp_path / "serial", options, jobs=1)
        }
        parallel = {
            r.dst.name: r.status
            for r in run(files, corpus, tmp_path / "parallel", options, jobs=4)
        }

        assert serial == parallel

    def test_one_bad_file_does_not_stop_the_batch(self, corpus: Path, tmp_path: Path):
        files = list(discover(corpus, ["jpg", "jpeg", "png"], recursive=True))
        results = list(run(files, corpus, tmp_path / "out", Options(), jobs=2))

        assert any(r.status is Status.FAILED for r in results)
        assert any(r.status is Status.CONVERTED for r in results)
        assert len(results) == len(files)
