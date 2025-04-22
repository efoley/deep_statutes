import dataclasses
import json
from pathlib import Path

import pymupdf

from deep_statutes.pdf.token_stream import (
    pdf_to_token_stream,
    PDFTokenConversionOptions,
)
from deep_statutes import config
from deep_statutes.states.co.clean_token_stream import clean_token_stream
from .parse_pdf import find_headers


DEFAULT_OPTIONS = PDFTokenConversionOptions(
    infer_centered=False,
    left_margin=72.0,
    indent_size=36.0,
    font_sizes=[float("inf"), 12.0, 20.0, float("inf")],
)


def write_token_stream(doc: pymupdf.Document, out_path: Path) -> None:
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


def write_raw_text(token_stream_path: Path, out_path: Path) -> None:
    with open(token_stream_path, "r") as file, open(out_path, "w") as out:
        with open(out_path, "w") as out:
            for line in file:
                if line.startswith("<<LINE"):
                    out.write("\n")
                elif line.startswith("<<"):
                    continue
                else:
                    out.write(line)
                    out.write("\n")


def main():
    input_dir = Path(config.STATUTES_DATA_DIR / "co" / "pdf")

    pdf_token_stream_dir = Path(
        config.STATUTES_DATA_DIR / "co" / "pdf" / "token_stream"
    )

    toc_dir = Path(config.STATUTES_DATA_DIR / "co" / "toc" / "from_token_stream")
    toc_dir.mkdir(parents=True, exist_ok=True)

    raw_text_dir = Path(config.STATUTES_DATA_DIR / "co" / "raw_text")
    raw_text_dir.mkdir(parents=True, exist_ok=True)

    # write token stream config
    pdf_token_stream_dir.mkdir(parents=True, exist_ok=True)
    with open(pdf_token_stream_dir / "config.json", "w") as file:
        json.dump(dataclasses.asdict(DEFAULT_OPTIONS), file, indent=4)

    for pdf_path in input_dir.glob("crs2024-title-*.pdf"):
        filename = pdf_path.stem
        # skip constitution for now
        if filename.endswith("-00.pdf"):
            continue
        token_stream_path = pdf_token_stream_dir / f"{filename}.txt"
        raw_text_path = raw_text_dir / f"{filename}.txt"
        toc_path = toc_dir / f"{filename}.md"

        print(f"{pdf_path} ->\n\t{token_stream_path}\n\t{toc_path}")

        doc = pymupdf.open(pdf_path)

        tmp_token_stream_path = token_stream_path.with_suffix(".tmp")
        write_token_stream(doc, tmp_token_stream_path)
        clean_token_stream(tmp_token_stream_path, token_stream_path)
        tmp_token_stream_path.unlink()
        write_toc(token_stream_path, toc_path)

        write_raw_text(token_stream_path, raw_text_path)
