from pathlib import Path
import tempfile

from lark import Lark
import pymupdf

from deep_statutes.lark.util import find_matches
from deep_statutes.pdf.token_stream import (
    PDFTokenConversionOptions,
    pdf_to_token_stream,
)


DEFAULT_OPTIONS = PDFTokenConversionOptions(
    infer_centered=False,
    left_margin=72.0,
    indent_size=36.0,
    font_sizes=[float("inf"), 12.0, 20.0, float("inf")],
    page_delimiters=True,
)


footer_grammar = r"""
footer: _crs2024 _page _uncert
_crs2024: _LINE _SPAN_M "Colorado Revised Statutes 2024"
_uncert: _LINE _INDENT* _SPAN_M "Uncertified Printout"
_page: _LINE _INDENT* _SPAN_M /Page\s+[1-9][0-9]*\s+of\s+[1-9][0-9]*/

_LINE: /<<LINE [a-zA-Z0-9(), ]+>>/
_INDENT: /<<INDENT>>/

_SPAN_M: /<<SPAN_M>>/

EOL: /\n/

%ignore EOL
"""


def _clean_token_stream(in_path: Path, out_path: Path) -> None:
    """
    Clean the token stream by removing footer lines.
    """
    lark = Lark(
        footer_grammar,
        start="footer",
        parser="lalr",
        propagate_positions=True,
    )

    with open(in_path, "r") as file:
        text = file.read()

    with open(out_path, "w") as f:
        text_idx = 0
        while text_idx < len(text):
            parses, end_pos = find_matches(text[text_idx:], "footer", lark)

            assert len(parses) <= 1

            if len(parses) == 1:
                next_text_idx = text_idx + end_pos[0]
                text_idx = next_text_idx
            else:
                # find next line
                next_nl_idx = text.find("\n", text_idx + 1)
                if next_nl_idx == -1:
                    break
                next_text_idx = next_nl_idx
                f.write(text[text_idx:next_text_idx])
                text_idx = next_text_idx


def _write_raw_token_stream(doc: pymupdf.Document, out_path: Path) -> None:
    with open(out_path, "w") as file:
        for token in pdf_to_token_stream(doc, DEFAULT_OPTIONS):
            file.write(token)
            file.write("\n")


def write_clean_token_stream(doc: pymupdf.Document, out_path: Path) -> None:
    """
    Write the token stream with headers and footers removed to the specified output path.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as temp_file:
        temp_path = Path(temp_file.name)
        _write_raw_token_stream(doc, temp_path)
        _clean_token_stream(in_path=temp_path, out_path=out_path)
