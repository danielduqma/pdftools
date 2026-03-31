# pdftools

CLI for common PDF operations. Runs standalone with `uv run` (no install needed).

## Usage

```bash
uv run pdf_tools.py <command> [options]
```

### `merge` — Merge multiple PDFs into one

```bash
uv run pdf_tools.py merge -i file1.pdf file2.pdf file3.pdf -o merged.pdf
```

### `2up` — Two pages per sheet

Places two consecutive pages side by side (rotated 90° CW) on a single portrait page.

```bash
# Single file
uv run pdf_tools.py 2up -i document.pdf -o document_2up.pdf

# Multiple files → output directory
uv run pdf_tools.py 2up -i *.pdf -o output_dir/
```

### `pad` — Pad page count to a multiple

Adds blank pages at the end so the total is a multiple of N.

```bash
# Single file
uv run pdf_tools.py pad -i document.pdf -o document_padded.pdf -m 4

# Multiple files → output directory
uv run pdf_tools.py pad -i *.pdf -o output_dir/ -m 4
```

### Multi-file mode (`2up`, `pad`)

When passing multiple files to `-i`, `-o` must be a directory. Output files keep the same name as the originals. Existing files are overwritten.
