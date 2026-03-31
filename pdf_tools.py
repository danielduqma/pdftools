#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf==6.9.2"]
# ///
"""PDF tools: merge, 2-up layout, and page padding."""

import argparse
import sys
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter, Transformation


def merge(inputs: list[Path], output: Path) -> None:
    writer = PdfWriter()
    for path in inputs:
        reader = PdfReader(path)
        for page in reader.pages:
            writer.add_page(page)
    with open(output, "wb") as f:
        writer.write(f)
    print(f"Fusionado {len(inputs)} PDFs → {output} ({len(writer.pages)} páginas)")


def two_up(input_path: Path, output: Path) -> None:
    reader = PdfReader(input_path)
    writer = PdfWriter()
    pages = reader.pages

    for i in range(0, len(pages), 2):
        first = pages[i]
        orig_w = float(first.mediabox.width)
        orig_h = float(first.mediabox.height)

        second = pages[i + 1] if i + 1 < len(pages) else None

        # Página de salida: mismo tamaño portrait que el original
        page_w = orig_w
        page_h = orig_h
        half_h = page_h / 2

        # Rotada 90° CW: (orig_w x orig_h) → (orig_h x orig_w)
        # Escalar para que quepa en (page_w x half_h)
        s = min(page_w / orig_h, half_h / orig_w)

        # Centrado
        cx = (page_w - orig_h * s) / 2
        cy_top = half_h + (half_h - orig_w * s) / 2
        cy_bot = (half_h - orig_w * s) / 2

        # Rotación 90° CW + escala: (x,y) → (s*y + tx, -s*x + s*orig_w + ty)
        # CTM (a, b, c, d, e, f): new_x = a*x + c*y + e, new_y = b*x + d*y + f
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

    with open(output, "wb") as f:
        writer.write(f)
    print(
        f"2-up: {len(pages)} páginas → {len(writer.pages)} páginas en {output}"
    )


def pad_multiple(input_path: Path, output: Path, multiple: int) -> None:
    reader = PdfReader(input_path)
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
    else:
        blanks_needed = 0

    with open(output, "wb") as f:
        writer.write(f)
    print(
        f"Redondeo: {total} + {blanks_needed} en blanco = "
        f"{total + blanks_needed} páginas (múltiplo de {multiple}) → {output}"
    )


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

    # pad
    p_pad = sub.add_parser("pad", help="Pad page count to a multiple")
    p_pad.add_argument("--input", "-i", nargs="+", required=True, type=Path,
                       help="Input PDFs")
    p_pad.add_argument("--output", "-o", required=True, type=Path,
                       help="Output PDF or directory (if multiple inputs)")
    p_pad.add_argument("--multiple", "-m", required=True, type=int,
                       help="Desired multiple (e.g. 4)")

    args = parser.parse_args()

    if args.command == "merge":
        for p in args.input:
            if not p.exists():
                sys.exit(f"Error: no existe {p}")
        merge(args.input, args.output)
    elif args.command in ("2up", "pad"):
        for p in args.input:
            if not p.exists():
                sys.exit(f"Error: no existe {p}")
        if args.command == "pad" and args.multiple < 2:
            sys.exit("Error: el múltiplo debe ser >= 2")

        if len(args.input) > 1:
            args.output.mkdir(parents=True, exist_ok=True)
            if not args.output.is_dir():
                sys.exit(f"Error: con varios inputs, -o debe ser una carpeta")

        func = two_up if args.command == "2up" else pad_multiple
        for inp in args.input:
            if len(args.input) == 1 and not args.output.is_dir():
                out = args.output
            else:
                out = args.output / inp.name
            if args.command == "2up":
                func(inp, out)
            else:
                func(inp, out, args.multiple)


if __name__ == "__main__":
    main()
