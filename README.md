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

### `delete` — Delete specific pages

Removes the specified pages from a PDF. Pages can be individual numbers, ranges, or a combination.

```bash
# Delete pages 1, 3, and 5 through 8
uv run pdf_tools.py delete -i document.pdf -o trimmed.pdf -p '1,3,5-8'

# Multiple files → output directory
uv run pdf_tools.py delete -i *.pdf -o output_dir/ -p '1'
```

### `pad` — Pad page count to a multiple

Adds blank pages at the end so the total is a multiple of N.

```bash
# Single file
uv run pdf_tools.py pad -i document.pdf -o document_padded.pdf -m 4

# Multiple files → output directory
uv run pdf_tools.py pad -i *.pdf -o output_dir/ -m 4
```

### `pipe` — Chain operations in a pipeline

Chains multiple operations in sequence, separated by `+`. Intermediate results stay in memory (no temp files).

```bash
uv run pdf_tools.py pipe -i a.pdf b.pdf -o result.pdf -- \
    delete -p 1 + pad -m 4 + 2up + merge
```

Available stages: `delete -p <pages>`, `pad -m <n>`, `2up`, `merge`.

- **Per-file operations** (`delete`, `pad`, `2up`) apply to each input independently.
- **`merge`** combines all inputs into one. After a merge, subsequent stages operate on the single result.
- Stages can appear in **any order**.

#### Per-file delete

By default, `delete` removes the same pages from all files. To delete different pages per file, prefix each `-p` with the file number (1-based):

```bash
# Delete page 1 from file #1, pages 3-5 from file #2
uv run pdf_tools.py pipe -i ch1.pdf ch2.pdf -o out/ -- \
    delete -p 1:1 -p 2:3-5 + pad -m 4
```

#### Examples

```bash
# Delete page 1 from each, pad to multiple of 4, 2-up layout, merge
uv run pdf_tools.py pipe -i ch1.pdf ch2.pdf ch3.pdf -o book.pdf -- \
    delete -p 1 + pad -m 4 + 2up + merge

# Merge first, then post-process
uv run pdf_tools.py pipe -i part1.pdf part2.pdf -o final.pdf -- \
    merge + delete -p 1,2 + pad -m 4 + 2up

# Per-file delete, then merge
uv run pdf_tools.py pipe -i a.pdf b.pdf -o combined.pdf -- \
    delete -p 1:1,2 -p 2:1 + merge
```

### Multi-file mode (`2up`, `pad`, `delete`)

When passing multiple files to `-i`, `-o` must be a directory. Output files keep the same name as the originals. Existing files are overwritten.
