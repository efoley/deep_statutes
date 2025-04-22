import dataclasses
import json
from pathlib import Path

import pymupdf

from deep_statutes.pdf.token_stream import (
    pdf_to_token_stream,
    PDFTokenConversionOptions,
)
from deep_statutes import config
from .parse_pdf import find_headers


DEFAULT_OPTIONS = PDFTokenConversionOptions(
    infer_centered=False,
    left_margin=72.0,
    indent_size=36.0,
    font_sizes=[float("inf"), 12.0, float("inf"), float("inf")],
)


def write_token_stream(doc: pymupdf.Document, out_path: Path) -> None:
    """
    Write the token stream to a file.
    """
    with open(out_path, "w") as file:
        for token in pdf_to_token_stream(doc, DEFAULT_OPTIONS):
            file.write(token)
            file.write("\n")


def write_toc(token_stream_path: Path, out_path: Path) -> None:
    headers = find_headers(token_stream_path)

    with open(out_path, "w") as out:
        for header in headers:
            level = header.type.value
            out.write("#" * level)
            out.write(" ")
            out.write(header.text)
            out.write(" - ")
            out.write(header.sub_text)
            out.write(f" ({header.text_range[0]}-{header.text_range[1]})")
            out.write("\n")


def main():
    input_dir = Path(config.STATUTES_DATA_DIR / "wy" / "pdf")

    pdf_token_stream_dir = Path(
        config.STATUTES_DATA_DIR / "wy" / "pdf" / "token_stream"
    )

    toc_dir = Path(config.STATUTES_DATA_DIR / "wy" / "toc" / "from_token_stream")
    toc_dir.mkdir(parents=True, exist_ok=True)

    # write token stream config
    pdf_token_stream_dir.mkdir(parents=True, exist_ok=True)
    with open(pdf_token_stream_dir / "config.json", "w") as file:
        file.write(json.dumps(dataclasses.asdict(DEFAULT_OPTIONS), indent=4))

    for filename in input_dir.iterdir():
        if filename.suffix == ".pdf":
            pdf_path = input_dir / filename
            token_stream_path = pdf_token_stream_dir / f"{filename.stem}.txt"
            toc_path = toc_dir / f"{filename.stem}.md"
            print(f"{pdf_path} ->\n\t{token_stream_path}\n\t{toc_path}")

            doc = pymupdf.open(pdf_path)

            write_token_stream(doc, token_stream_path)

            write_toc(token_stream_path, toc_path)
