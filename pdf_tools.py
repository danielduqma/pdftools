#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf==6.9.2"]
# ///
"""PDF tools: merge, 2-up layout, page padding, page deletion, and pipelines."""

import argparse
import sys
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter, Transformation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _writer_to_buffer(writer: PdfWriter) -> BytesIO:
    """Serialize a PdfWriter to an in-memory buffer."""
    buf = BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Core functions (BytesIO → BytesIO)
# ---------------------------------------------------------------------------

def merge_core(inputs: list[BytesIO]) -> BytesIO:
    writer = PdfWriter()
    for inp in inputs:
        reader = PdfReader(inp)
        for page in reader.pages:
            writer.add_page(page)
    return _writer_to_buffer(writer)


def two_up_core(input_buf: BytesIO) -> BytesIO:
    reader = PdfReader(input_buf)
    writer = PdfWriter()
    pages = reader.pages

    for i in range(0, len(pages), 2):
        first = pages[i]
        orig_w = float(first.mediabox.width)
        orig_h = float(first.mediabox.height)

        second = pages[i + 1] if i + 1 < len(pages) else None

        page_w = orig_w
        page_h = orig_h
        half_h = page_h / 2

        s = min(page_w / orig_h, half_h / orig_w)

        cx = (page_w - orig_h * s) / 2
        cy_top = half_h + (half_h - orig_w * s) / 2
        cy_bot = (half_h - orig_w * s) / 2

        new_page = PageObject.create_blank_page(width=page_w, height=page_h)

        new_page.merge_transformed_page(
            first,
            Transformation(ctm=(0, -s, s, 0, cx, s * orig_w + cy_top)),
        )
        if second:
            new_page.merge_transformed_page(
                second,
                Transformation(ctm=(0, -s, s, 0, cx, s * orig_w + cy_bot)),
            )

        writer.add_page(new_page)

    return _writer_to_buffer(writer)


def pad_multiple_core(input_buf: BytesIO, multiple: int) -> BytesIO:
    reader = PdfReader(input_buf)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    total = len(reader.pages)
    remainder = total % multiple
    if remainder:
        blanks_needed = multiple - remainder
        last = reader.pages[-1]
        w = float(last.mediabox.width)
        h = float(last.mediabox.height)
        for _ in range(blanks_needed):
            writer.add_blank_page(width=w, height=h)

    return _writer_to_buffer(writer)


def delete_pages_core(input_buf: BytesIO, pages_spec: str) -> BytesIO:
    reader = PdfReader(input_buf)
    total = len(reader.pages)
    to_delete = parse_pages(pages_spec, total)

    if len(to_delete) >= total:
        sys.exit("Error: no se pueden eliminar todas las páginas")

    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i not in to_delete:
            writer.add_page(page)

    return _writer_to_buffer(writer)


def parse_pages(spec: str, total: int) -> set[int]:
    """Parse a page specification like '1,3,5-8' into a set of 0-based indices."""
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start_i, end_i = int(start), int(end)
            if start_i < 1 or end_i > total or start_i > end_i:
                sys.exit(f"Error: rango inválido {part} (el PDF tiene {total} páginas)")
            pages.update(range(start_i - 1, end_i))
        else:
            n = int(part)
            if n < 1 or n > total:
                sys.exit(f"Error: página {n} fuera de rango (el PDF tiene {total} páginas)")
            pages.add(n - 1)
    return pages


# ---------------------------------------------------------------------------
# Disk wrappers (Path → Path, for standalone subcommands)
# ---------------------------------------------------------------------------

def merge(inputs: list[Path], output: Path) -> None:
    buffers = [BytesIO(p.read_bytes()) for p in inputs]
    result = merge_core(buffers)
    total_pages = len(PdfReader(result).pages)
    result.seek(0)
    output.write_bytes(result.getvalue())
    print(f"Fusionado {len(inputs)} PDFs → {output} ({total_pages} páginas)")


def two_up(input_path: Path, output: Path) -> None:
    input_buf = BytesIO(input_path.read_bytes())
    src_pages = len(PdfReader(input_buf).pages)
    input_buf.seek(0)
    result = two_up_core(input_buf)
    out_pages = len(PdfReader(result).pages)
    result.seek(0)
    output.write_bytes(result.getvalue())
    print(f"2-up: {src_pages} páginas → {out_pages} páginas en {output}")


def pad_multiple(input_path: Path, output: Path, multiple: int) -> None:
    input_buf = BytesIO(input_path.read_bytes())
    total = len(PdfReader(input_buf).pages)
    input_buf.seek(0)
    result = pad_multiple_core(input_buf, multiple)
    final_pages = len(PdfReader(result).pages)
    blanks_needed = final_pages - total
    result.seek(0)
    output.write_bytes(result.getvalue())
    print(
        f"Redondeo: {total} + {blanks_needed} en blanco = "
        f"{final_pages} páginas (múltiplo de {multiple}) → {output}"
    )


def delete_pages(input_path: Path, output: Path, pages_spec: str) -> None:
    input_buf = BytesIO(input_path.read_bytes())
    total = len(PdfReader(input_buf).pages)
    input_buf.seek(0)
    result = delete_pages_core(input_buf, pages_spec)
    remaining = len(PdfReader(result).pages)
    deleted = total - remaining
    result.seek(0)
    output.write_bytes(result.getvalue())
    print(
        f"Eliminadas {deleted} páginas de {total} → "
        f"{remaining} páginas en {output}"
    )


# ---------------------------------------------------------------------------
# Pipeline engine
# ---------------------------------------------------------------------------

@dataclass
class PipelineStage:
    command: str
    params: dict = field(default_factory=dict)


def parse_pipeline(tokens: list[str]) -> list[PipelineStage]:
    """Split tokens by '+' and parse each stage."""
    stages: list[PipelineStage] = []
    current: list[str] = []
    for token in tokens:
        if token == "+":
            if current:
                stages.append(_parse_stage(current))
                current = []
        else:
            current.append(token)
    if current:
        stages.append(_parse_stage(current))
    return stages


def _parse_stage(tokens: list[str]) -> PipelineStage:
    cmd = tokens[0]
    params: dict = {}
    page_specs: list[str] = []
    i = 1
    while i < len(tokens):
        if tokens[i] in ("-p", "--pages") and cmd == "delete":
            page_specs.append(tokens[i + 1])
            i += 2
        elif tokens[i] in ("-m", "--multiple") and cmd == "pad":
            params["multiple"] = int(tokens[i + 1])
            i += 2
        else:
            sys.exit(f"Error: argumento inesperado '{tokens[i]}' para '{cmd}'")
    if page_specs:
        has_prefix = any(":" in s for s in page_specs)
        if has_prefix:
            per_file: dict[int, str] = {}
            for spec in page_specs:
                if ":" not in spec:
                    sys.exit(
                        f"Error: al usar delete per-file, todos los -p deben "
                        f"llevar prefijo <n>: (encontrado '{spec}')"
                    )
                idx_str, pages = spec.split(":", 1)
                per_file[int(idx_str)] = pages
            params["pages"] = per_file
        else:
            if len(page_specs) > 1:
                sys.exit("Error: delete global solo acepta un -p (usa <n>: para per-file)")
            params["pages"] = page_specs[0]
    return PipelineStage(command=cmd, params=params)


def validate_pipeline(stages: list[PipelineStage]) -> None:
    if not stages:
        sys.exit("Error: el pipeline no puede estar vacío")
    for stage in stages:
        if stage.command not in ("merge", "2up", "pad", "delete"):
            sys.exit(f"Error: comando desconocido '{stage.command}'")
        if stage.command == "delete" and "pages" not in stage.params:
            sys.exit("Error: 'delete' requiere -p/--pages")
        if stage.command == "pad" and "multiple" not in stage.params:
            sys.exit("Error: 'pad' requiere -m/--multiple")
        if stage.command == "pad" and stage.params["multiple"] < 2:
            sys.exit("Error: el múltiplo debe ser >= 2")


def run_pipeline(inputs: list[Path], output: Path, stages: list[PipelineStage]) -> None:
    buffers = [BytesIO(p.read_bytes()) for p in inputs]

    for stage in stages:
        if stage.command == "merge":
            buffers = [merge_core(buffers)]
        elif stage.command == "2up":
            buffers = [two_up_core(b) for b in buffers]
        elif stage.command == "pad":
            buffers = [pad_multiple_core(b, stage.params["multiple"]) for b in buffers]
        elif stage.command == "delete":
            pages = stage.params["pages"]
            if isinstance(pages, dict):
                new_buffers = []
                for idx, buf in enumerate(buffers):
                    file_num = idx + 1
                    if file_num in pages:
                        new_buffers.append(delete_pages_core(buf, pages[file_num]))
                    else:
                        new_buffers.append(buf)
                buffers = new_buffers
            else:
                buffers = [delete_pages_core(b, pages) for b in buffers]

    if len(buffers) == 1:
        output.write_bytes(buffers[0].getvalue())
    else:
        output.mkdir(parents=True, exist_ok=True)
        for inp, buf in zip(inputs, buffers):
            (output / inp.name).write_bytes(buf.getvalue())

    print(f"Pipeline: {len(stages)} etapas → {output}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="PDF tools")
    sub = parser.add_subparsers(dest="command", required=True)

    # merge
    p_merge = sub.add_parser("merge", help="Merge multiple PDFs into one")
    p_merge.add_argument("--input", "-i", nargs="+", required=True, type=Path,
                         help="Input PDFs")
    p_merge.add_argument("--output", "-o", required=True, type=Path,
                         help="Output PDF")

    # 2-up
    p_2up = sub.add_parser("2up", help="Two pages per sheet")
    p_2up.add_argument("--input", "-i", nargs="+", required=True, type=Path,
                       help="Input PDFs")
    p_2up.add_argument("--output", "-o", required=True, type=Path,
                       help="Output PDF or directory (if multiple inputs)")

    # delete
    p_del = sub.add_parser("delete", help="Delete specific pages from a PDF")
    p_del.add_argument("--input", "-i", nargs="+", required=True, type=Path,
                       help="Input PDFs")
    p_del.add_argument("--output", "-o", required=True, type=Path,
                       help="Output PDF or directory (if multiple inputs)")
    p_del.add_argument("--pages", "-p", required=True, type=str,
                       help="Pages to delete (e.g. '1,3,5-8')")

    # pad
    p_pad = sub.add_parser("pad", help="Pad page count to a multiple")
    p_pad.add_argument("--input", "-i", nargs="+", required=True, type=Path,
                       help="Input PDFs")
    p_pad.add_argument("--output", "-o", required=True, type=Path,
                       help="Output PDF or directory (if multiple inputs)")
    p_pad.add_argument("--multiple", "-m", required=True, type=int,
                       help="Desired multiple (e.g. 4)")

    # pipe
    p_pipe = sub.add_parser(
        "pipe",
        help="Chain operations in a pipeline",
        description=(
            "Chain multiple operations separated by +. "
            "Available stages: delete -p <pages>, pad -m <n>, 2up, merge. "
            "delete supports per-file mode: -p 1:<pages> -p 2:<pages>."
        ),
    )
    p_pipe.add_argument("--input", "-i", nargs="+", required=True, type=Path,
                        help="Input PDFs")
    p_pipe.add_argument("--output", "-o", required=True, type=Path,
                        help="Output PDF or directory")
    p_pipe.add_argument("pipeline", nargs=argparse.REMAINDER,
                        help="Pipeline stages separated by +")

    args = parser.parse_args()

    if args.command == "merge":
        for p in args.input:
            if not p.exists():
                sys.exit(f"Error: no existe {p}")
        merge(args.input, args.output)
    elif args.command == "pipe":
        for p in args.input:
            if not p.exists():
                sys.exit(f"Error: no existe {p}")
        tokens = args.pipeline
        if tokens and tokens[0] == "--":
            tokens = tokens[1:]
        stages = parse_pipeline(tokens)
        validate_pipeline(stages)
        run_pipeline(args.input, args.output, stages)
    elif args.command in ("2up", "pad", "delete"):
        for p in args.input:
            if not p.exists():
                sys.exit(f"Error: no existe {p}")
        if args.command == "pad" and args.multiple < 2:
            sys.exit("Error: el múltiplo debe ser >= 2")

        if len(args.input) > 1:
            args.output.mkdir(parents=True, exist_ok=True)
            if not args.output.is_dir():
                sys.exit(f"Error: con varios inputs, -o debe ser una carpeta")

        for inp in args.input:
            if len(args.input) == 1 and not args.output.is_dir():
                out = args.output
            else:
                out = args.output / inp.name
            if args.command == "2up":
                two_up(inp, out)
            elif args.command == "delete":
                delete_pages(inp, out, args.pages)
            else:
                pad_multiple(inp, out, args.multiple)


if __name__ == "__main__":
    main()
