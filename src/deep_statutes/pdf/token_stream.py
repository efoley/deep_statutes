from pathlib import Path
from dataclasses import dataclass
from typing import Iterator, Literal

import pymupdf
from deep_statutes.pdf.util import SpanDict
from deep_statutes.pdf.util import is_bbox_centered, get_bbox_indent_level

MAGIC_TEMPLATE = "<<{}>>"


def _to_magic(text: str) -> str:
    return MAGIC_TEMPLATE.format(text)


def _concise_font_size(
    size: float, font_sizes: tuple[float, float, float, float]
) -> Literal["S", "M", "L", "XL"]:
    dist = [abs(size - fs) for fs in font_sizes]
    min_idx = dist.index(min(dist))
    return ["S", "M", "L", "XL"][min_idx]


@dataclass(kw_only=True)
class PDFTokenConversionOptions:
    left_margin: float
    indent_size: float

    # note: may have false positives but can be useful for
    # finding headings
    infer_centered: bool = False

    font_sizes: tuple[float, float, float, float]

    page_delimiters: bool = False
    block_delimiters: bool = False


def pdf_to_token_stream(
    doc: str | Path | pymupdf.Document, options: PDFTokenConversionOptions
) -> Iterator[str]:
    global_line_idx = 0

    if not isinstance(doc, pymupdf.Document):
        doc = pymupdf.open(doc)

    for page_idx, page in enumerate(doc):
        if options.page_delimiters:
            yield _to_magic(f"PAGE {page_idx}")
        d = page.get_text("dict")
        page_width = d["width"]
        blocks = d["blocks"]
        for block_idx, block in enumerate(blocks):
            if options.block_delimiters:
                yield _to_magic(f"BLOCK {(page_idx, block_idx)}")
            for line_idx, line in enumerate(block["lines"]):
                yield _to_magic(f"LINE {(page_idx, block_idx, line_idx)}")

                if options.infer_centered and is_bbox_centered(
                    line["bbox"], page_width
                ):
                    yield _to_magic("CENTER"),
                else:
                    indent = get_bbox_indent_level(
                        line["bbox"],
                        left_margin=options.left_margin,
                        indent_size=options.indent_size,
                    )

                    for _ in range(indent):
                        yield _to_magic("INDENT")

                for span_idx, span in enumerate(line["spans"]):
                    span: SpanDict
                    span_text = span["text"]

                    # note that we completely skip empty spans
                    if span_text.strip() == "":
                        continue

                    is_bold = "bold" in span["font"].lower()
                    size = _concise_font_size(span["size"], options.font_sizes)
                    span_tok = f"SPAN_{size}"
                    if is_bold:
                        span_tok += "_B"
                    yield _to_magic(span_tok)
                    yield span_text

                global_line_idx += 1


# def main():
#    parser = argparse.ArgumentParser(description="Convert PDF to token stream")
#    parser.add_argument("pdf_path", help="Path to the PDF file")
#    parser.add_argument('--output', '-o', default=None, help='Output path')
#    args = parser.parse_args()
#
#    doc = pymupdf.open(args.pdf_path)
#
#    options = PDFTokenConversionOptions(
#
#    f = open(args.output, 'w') if args.output else sys.stdout
#    for token in pdf_to_token_stream(doc):
#        f.write(token + '\n')
#    if f != sys.stdout:
#        f.close()
