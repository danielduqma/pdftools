"""Tests for pdf_tools."""

import io
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from pdf_tools import (
    PipelineStage,
    delete_pages,
    delete_pages_core,
    merge,
    merge_core,
    pad_multiple,
    pad_multiple_core,
    parse_pages,
    parse_pipeline,
    run_pipeline,
    two_up,
    two_up_core,
    validate_pipeline,
)


def _make_pdf(num_pages: int, path: Path) -> Path:
    """Create a simple PDF with the given number of blank pages."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)  # Letter size
    with open(path, "wb") as f:
        writer.write(f)
    return path


def _make_pdf_buf(num_pages: int) -> io.BytesIO:
    """Create a simple in-memory PDF with the given number of blank pages."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf


def _buf_page_count(buf: io.BytesIO) -> int:
    buf.seek(0)
    return len(PdfReader(buf).pages)


def _page_count(path: Path) -> int:
    return len(PdfReader(path).pages)


# --- parse_pages ---


class TestParsePages:
    def test_single_page(self):
        assert parse_pages("3", 5) == {2}

    def test_multiple_pages(self):
        assert parse_pages("1,3,5", 5) == {0, 2, 4}

    def test_range(self):
        assert parse_pages("2-4", 5) == {1, 2, 3}

    def test_mixed(self):
        assert parse_pages("1,3-5", 6) == {0, 2, 3, 4}

    def test_spaces_are_stripped(self):
        assert parse_pages(" 1 , 3 ", 5) == {0, 2}

    def test_page_out_of_range_exits(self):
        with pytest.raises(SystemExit):
            parse_pages("6", 5)

    def test_page_zero_exits(self):
        with pytest.raises(SystemExit):
            parse_pages("0", 5)

    def test_invalid_range_exits(self):
        with pytest.raises(SystemExit):
            parse_pages("4-2", 5)

    def test_range_exceeds_total_exits(self):
        with pytest.raises(SystemExit):
            parse_pages("3-10", 5)


# --- merge ---


class TestMerge:
    def test_merge_two_files(self, tmp_path):
        a = _make_pdf(2, tmp_path / "a.pdf")
        b = _make_pdf(3, tmp_path / "b.pdf")
        out = tmp_path / "merged.pdf"
        merge([a, b], out)
        assert _page_count(out) == 5

    def test_merge_single_file(self, tmp_path):
        a = _make_pdf(4, tmp_path / "a.pdf")
        out = tmp_path / "merged.pdf"
        merge([a], out)
        assert _page_count(out) == 4

    def test_merge_many_files(self, tmp_path):
        pdfs = [_make_pdf(1, tmp_path / f"{i}.pdf") for i in range(5)]
        out = tmp_path / "merged.pdf"
        merge(pdfs, out)
        assert _page_count(out) == 5


# --- two_up ---


class TestTwoUp:
    def test_even_pages(self, tmp_path):
        src = _make_pdf(4, tmp_path / "input.pdf")
        out = tmp_path / "2up.pdf"
        two_up(src, out)
        assert _page_count(out) == 2

    def test_odd_pages(self, tmp_path):
        src = _make_pdf(5, tmp_path / "input.pdf")
        out = tmp_path / "2up.pdf"
        two_up(src, out)
        assert _page_count(out) == 3

    def test_single_page(self, tmp_path):
        src = _make_pdf(1, tmp_path / "input.pdf")
        out = tmp_path / "2up.pdf"
        two_up(src, out)
        assert _page_count(out) == 1

    def test_output_page_dimensions(self, tmp_path):
        src = _make_pdf(2, tmp_path / "input.pdf")
        out = tmp_path / "2up.pdf"
        two_up(src, out)
        reader = PdfReader(out)
        page = reader.pages[0]
        assert float(page.mediabox.width) == pytest.approx(612)
        assert float(page.mediabox.height) == pytest.approx(792)


# --- pad_multiple ---


class TestPadMultiple:
    def test_needs_padding(self, tmp_path):
        src = _make_pdf(5, tmp_path / "input.pdf")
        out = tmp_path / "padded.pdf"
        pad_multiple(src, out, 4)
        assert _page_count(out) == 8

    def test_already_multiple(self, tmp_path):
        src = _make_pdf(8, tmp_path / "input.pdf")
        out = tmp_path / "padded.pdf"
        pad_multiple(src, out, 4)
        assert _page_count(out) == 8

    def test_pad_to_2(self, tmp_path):
        src = _make_pdf(3, tmp_path / "input.pdf")
        out = tmp_path / "padded.pdf"
        pad_multiple(src, out, 2)
        assert _page_count(out) == 4

    def test_single_page_pad(self, tmp_path):
        src = _make_pdf(1, tmp_path / "input.pdf")
        out = tmp_path / "padded.pdf"
        pad_multiple(src, out, 4)
        assert _page_count(out) == 4


# --- delete_pages ---


class TestDeletePages:
    def test_delete_single_page(self, tmp_path):
        src = _make_pdf(5, tmp_path / "input.pdf")
        out = tmp_path / "output.pdf"
        delete_pages(src, out, "3")
        assert _page_count(out) == 4

    def test_delete_multiple_pages(self, tmp_path):
        src = _make_pdf(5, tmp_path / "input.pdf")
        out = tmp_path / "output.pdf"
        delete_pages(src, out, "1,3,5")
        assert _page_count(out) == 2

    def test_delete_range(self, tmp_path):
        src = _make_pdf(6, tmp_path / "input.pdf")
        out = tmp_path / "output.pdf"
        delete_pages(src, out, "2-4")
        assert _page_count(out) == 3

    def test_delete_mixed(self, tmp_path):
        src = _make_pdf(8, tmp_path / "input.pdf")
        out = tmp_path / "output.pdf"
        delete_pages(src, out, "1,3-5,8")
        assert _page_count(out) == 3

    def test_delete_all_pages_exits(self, tmp_path):
        src = _make_pdf(3, tmp_path / "input.pdf")
        out = tmp_path / "output.pdf"
        with pytest.raises(SystemExit):
            delete_pages(src, out, "1-3")

    def test_delete_first_page(self, tmp_path):
        src = _make_pdf(3, tmp_path / "input.pdf")
        out = tmp_path / "output.pdf"
        delete_pages(src, out, "1")
        assert _page_count(out) == 2

    def test_delete_last_page(self, tmp_path):
        src = _make_pdf(3, tmp_path / "input.pdf")
        out = tmp_path / "output.pdf"
        delete_pages(src, out, "3")
        assert _page_count(out) == 2


# --- CLI (main) ---


class TestCLI:
    def test_merge_cli(self, tmp_path, monkeypatch):
        a = _make_pdf(2, tmp_path / "a.pdf")
        b = _make_pdf(3, tmp_path / "b.pdf")
        out = tmp_path / "merged.pdf"
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "merge", "-i", str(a), str(b), "-o", str(out)],
        )
        from pdf_tools import main
        main()
        assert _page_count(out) == 5

    def test_2up_cli(self, tmp_path, monkeypatch):
        src = _make_pdf(4, tmp_path / "input.pdf")
        out = tmp_path / "2up.pdf"
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "2up", "-i", str(src), "-o", str(out)],
        )
        from pdf_tools import main
        main()
        assert _page_count(out) == 2

    def test_pad_cli(self, tmp_path, monkeypatch):
        src = _make_pdf(5, tmp_path / "input.pdf")
        out = tmp_path / "padded.pdf"
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "pad", "-i", str(src), "-o", str(out), "-m", "4"],
        )
        from pdf_tools import main
        main()
        assert _page_count(out) == 8

    def test_delete_cli(self, tmp_path, monkeypatch):
        src = _make_pdf(5, tmp_path / "input.pdf")
        out = tmp_path / "output.pdf"
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "delete", "-i", str(src), "-o", str(out), "-p", "1,3"],
        )
        from pdf_tools import main
        main()
        assert _page_count(out) == 3

    def test_missing_input_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "merge", "-i", str(tmp_path / "nope.pdf"), "-o", str(tmp_path / "out.pdf")],
        )
        from pdf_tools import main
        with pytest.raises(SystemExit):
            main()

    def test_multiple_inputs_to_directory(self, tmp_path, monkeypatch):
        a = _make_pdf(4, tmp_path / "a.pdf")
        b = _make_pdf(6, tmp_path / "b.pdf")
        out_dir = tmp_path / "output"
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "delete", "-i", str(a), str(b), "-o", str(out_dir), "-p", "1"],
        )
        from pdf_tools import main
        main()
        assert _page_count(out_dir / "a.pdf") == 3
        assert _page_count(out_dir / "b.pdf") == 5


# --- Core functions (BytesIO) ---


class TestMergeCore:
    def test_merge_two_buffers(self):
        result = merge_core([_make_pdf_buf(2), _make_pdf_buf(3)])
        assert _buf_page_count(result) == 5

    def test_merge_single_buffer(self):
        result = merge_core([_make_pdf_buf(4)])
        assert _buf_page_count(result) == 4


class TestTwoUpCore:
    def test_even_pages(self):
        result = two_up_core(_make_pdf_buf(4))
        assert _buf_page_count(result) == 2

    def test_odd_pages(self):
        result = two_up_core(_make_pdf_buf(5))
        assert _buf_page_count(result) == 3

    def test_single_page(self):
        result = two_up_core(_make_pdf_buf(1))
        assert _buf_page_count(result) == 1


class TestPadMultipleCore:
    def test_needs_padding(self):
        result = pad_multiple_core(_make_pdf_buf(5), 4)
        assert _buf_page_count(result) == 8

    def test_already_multiple(self):
        result = pad_multiple_core(_make_pdf_buf(8), 4)
        assert _buf_page_count(result) == 8


class TestDeletePagesCore:
    def test_delete_single(self):
        result = delete_pages_core(_make_pdf_buf(5), "2")
        assert _buf_page_count(result) == 4

    def test_delete_range(self):
        result = delete_pages_core(_make_pdf_buf(6), "2-4")
        assert _buf_page_count(result) == 3

    def test_delete_all_exits(self):
        with pytest.raises(SystemExit):
            delete_pages_core(_make_pdf_buf(3), "1-3")


# --- Pipeline parsing & validation ---


class TestParsePipeline:
    def test_single_stage(self):
        stages = parse_pipeline(["2up"])
        assert len(stages) == 1
        assert stages[0].command == "2up"

    def test_multiple_stages(self):
        stages = parse_pipeline(["delete", "-p", "1", "+", "pad", "-m", "4", "+", "merge"])
        assert len(stages) == 3
        assert stages[0].command == "delete"
        assert stages[0].params == {"pages": "1"}
        assert stages[1].command == "pad"
        assert stages[1].params == {"multiple": 4}
        assert stages[2].command == "merge"

    def test_long_page_flags(self):
        stages = parse_pipeline(["delete", "--pages", "1,3"])
        assert stages[0].params == {"pages": "1,3"}

    def test_long_multiple_flag(self):
        stages = parse_pipeline(["pad", "--multiple", "8"])
        assert stages[0].params == {"multiple": 8}

    def test_unknown_arg_exits(self):
        with pytest.raises(SystemExit):
            parse_pipeline(["2up", "--foo"])

    def test_per_file_delete(self):
        stages = parse_pipeline(["delete", "-p", "1:1,3", "-p", "2:2-4"])
        assert stages[0].command == "delete"
        assert stages[0].params == {"pages": {1: "1,3", 2: "2-4"}}

    def test_per_file_delete_long_flag(self):
        stages = parse_pipeline(["delete", "--pages", "1:1", "--pages", "2:5"])
        assert stages[0].params == {"pages": {1: "1", 2: "5"}}

    def test_mixed_global_and_per_file_exits(self):
        with pytest.raises(SystemExit):
            parse_pipeline(["delete", "-p", "1:1,3", "-p", "2"])

    def test_multiple_global_pages_exits(self):
        with pytest.raises(SystemExit):
            parse_pipeline(["delete", "-p", "1", "-p", "2"])


class TestValidatePipeline:
    def test_empty_pipeline_exits(self):
        with pytest.raises(SystemExit):
            validate_pipeline([])

    def test_unknown_command_exits(self):
        with pytest.raises(SystemExit):
            validate_pipeline([PipelineStage(command="unknown")])

    def test_delete_without_pages_exits(self):
        with pytest.raises(SystemExit):
            validate_pipeline([PipelineStage(command="delete")])

    def test_pad_without_multiple_exits(self):
        with pytest.raises(SystemExit):
            validate_pipeline([PipelineStage(command="pad")])

    def test_pad_multiple_too_low_exits(self):
        with pytest.raises(SystemExit):
            validate_pipeline([PipelineStage(command="pad", params={"multiple": 1})])

    def test_valid_pipeline_passes(self):
        validate_pipeline([
            PipelineStage(command="delete", params={"pages": "1"}),
            PipelineStage(command="pad", params={"multiple": 4}),
            PipelineStage(command="2up"),
            PipelineStage(command="merge"),
        ])


# --- Pipeline execution ---


class TestRunPipeline:
    def test_single_stage_delete(self, tmp_path):
        src = _make_pdf(5, tmp_path / "input.pdf")
        out = tmp_path / "out.pdf"
        stages = [PipelineStage(command="delete", params={"pages": "1"})]
        run_pipeline([src], out, stages)
        assert _page_count(out) == 4

    def test_single_stage_2up(self, tmp_path):
        src = _make_pdf(4, tmp_path / "input.pdf")
        out = tmp_path / "out.pdf"
        stages = [PipelineStage(command="2up")]
        run_pipeline([src], out, stages)
        assert _page_count(out) == 2

    def test_merge_then_delete(self, tmp_path):
        a = _make_pdf(3, tmp_path / "a.pdf")
        b = _make_pdf(3, tmp_path / "b.pdf")
        out = tmp_path / "out.pdf"
        stages = [
            PipelineStage(command="merge"),
            PipelineStage(command="delete", params={"pages": "1"}),
        ]
        run_pipeline([a, b], out, stages)
        assert _page_count(out) == 5

    def test_full_pipeline(self, tmp_path):
        a = _make_pdf(5, tmp_path / "a.pdf")
        b = _make_pdf(5, tmp_path / "b.pdf")
        out = tmp_path / "out.pdf"
        # delete page 1 from each (4 each) → pad to 4 (already 4) → 2up (2 each) → merge (4 total)
        stages = [
            PipelineStage(command="delete", params={"pages": "1"}),
            PipelineStage(command="pad", params={"multiple": 4}),
            PipelineStage(command="2up"),
            PipelineStage(command="merge"),
        ]
        run_pipeline([a, b], out, stages)
        assert _page_count(out) == 4

    def test_per_file_ops_output_directory(self, tmp_path):
        a = _make_pdf(5, tmp_path / "a.pdf")
        b = _make_pdf(3, tmp_path / "b.pdf")
        out_dir = tmp_path / "output"
        stages = [PipelineStage(command="delete", params={"pages": "1"})]
        run_pipeline([a, b], out_dir, stages)
        assert _page_count(out_dir / "a.pdf") == 4
        assert _page_count(out_dir / "b.pdf") == 2

    def test_merge_with_single_file(self, tmp_path):
        src = _make_pdf(3, tmp_path / "input.pdf")
        out = tmp_path / "out.pdf"
        stages = [PipelineStage(command="merge")]
        run_pipeline([src], out, stages)
        assert _page_count(out) == 3

    def test_pipeline_pad_then_2up(self, tmp_path):
        src = _make_pdf(3, tmp_path / "input.pdf")
        out = tmp_path / "out.pdf"
        # 3 pages → pad to 4 → 2up → 2 pages
        stages = [
            PipelineStage(command="pad", params={"multiple": 4}),
            PipelineStage(command="2up"),
        ]
        run_pipeline([src], out, stages)
        assert _page_count(out) == 2

    def test_per_file_delete(self, tmp_path):
        a = _make_pdf(5, tmp_path / "a.pdf")
        b = _make_pdf(4, tmp_path / "b.pdf")
        out_dir = tmp_path / "output"
        # Delete pages 1,2 from file #1 (5→3), delete page 1 from file #2 (4→3)
        stages = [PipelineStage(command="delete", params={"pages": {1: "1,2", 2: "1"}})]
        run_pipeline([a, b], out_dir, stages)
        assert _page_count(out_dir / "a.pdf") == 3
        assert _page_count(out_dir / "b.pdf") == 3

    def test_per_file_delete_skips_unmentioned(self, tmp_path):
        a = _make_pdf(5, tmp_path / "a.pdf")
        b = _make_pdf(4, tmp_path / "b.pdf")
        out_dir = tmp_path / "output"
        # Only delete from file #1, file #2 untouched
        stages = [PipelineStage(command="delete", params={"pages": {1: "1"}})]
        run_pipeline([a, b], out_dir, stages)
        assert _page_count(out_dir / "a.pdf") == 4
        assert _page_count(out_dir / "b.pdf") == 4

    def test_per_file_delete_then_merge(self, tmp_path):
        a = _make_pdf(5, tmp_path / "a.pdf")
        b = _make_pdf(3, tmp_path / "b.pdf")
        out = tmp_path / "out.pdf"
        stages = [
            PipelineStage(command="delete", params={"pages": {1: "1,2", 2: "1"}}),
            PipelineStage(command="merge"),
        ]
        run_pipeline([a, b], out, stages)
        # a: 5-2=3, b: 3-1=2, merged: 5
        assert _page_count(out) == 5


# --- CLI pipe subcommand ---


class TestPipeCLI:
    def test_pipe_cli_basic(self, tmp_path, monkeypatch):
        src = _make_pdf(5, tmp_path / "input.pdf")
        out = tmp_path / "out.pdf"
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "pipe", "-i", str(src), "-o", str(out),
             "--", "delete", "-p", "1", "+", "pad", "-m", "4"],
        )
        from pdf_tools import main
        main()
        assert _page_count(out) == 4

    def test_pipe_cli_full_chain(self, tmp_path, monkeypatch):
        a = _make_pdf(5, tmp_path / "a.pdf")
        b = _make_pdf(5, tmp_path / "b.pdf")
        out = tmp_path / "out.pdf"
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "pipe", "-i", str(a), str(b), "-o", str(out),
             "--", "delete", "-p", "1", "+", "pad", "-m", "4",
             "+", "2up", "+", "merge"],
        )
        from pdf_tools import main
        main()
        assert _page_count(out) == 4

    def test_pipe_cli_per_file_delete(self, tmp_path, monkeypatch):
        a = _make_pdf(5, tmp_path / "a.pdf")
        b = _make_pdf(4, tmp_path / "b.pdf")
        out = tmp_path / "out.pdf"
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "pipe", "-i", str(a), str(b), "-o", str(out),
             "--", "delete", "-p", "1:1,2", "-p", "2:1", "+", "merge"],
        )
        from pdf_tools import main
        main()
        # a: 5-2=3, b: 4-1=3, merged: 6
        assert _page_count(out) == 6

    def test_pipe_cli_missing_input_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_tools.py", "pipe", "-i", str(tmp_path / "nope.pdf"),
             "-o", str(tmp_path / "out.pdf"), "--", "2up"],
        )
        from pdf_tools import main
        with pytest.raises(SystemExit):
            main()
