import io
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

import pymupdf
from lark import Lark, Tree

from deep_statutes.pdf.token_stream import (
    pdf_to_token_stream,
    PDFTokenConversionOptions,
)
from deep_statutes import config
from deep_statutes.pdf.util import Pos
from deep_statutes.lark import find_matches


DEFAULT_OPTIONS = PDFTokenConversionOptions(
    infer_centered=False,
    left_margin=72.0,
    indent_size=36.0,
    font_sizes=[float("inf"), 12.0, float("inf"), float("inf")],
)


class HeadingType(Enum):
    Title = auto()
    Chapter = auto()
    Article = auto()
    Section = auto()


@dataclass
class Heading:
    type: HeadingType
    text: str
    sub_text: str
    pos: Pos


def _child(tree: Tree, idx: int, name: str) -> Tree:
    child_tree = tree.children[idx]
    if child_tree.data != name:
        raise ValueError(f"Expected {name}, got {child_tree.data}")
    return child_tree


def _text(tree: Tree):
    """
    Get all text from the tree's children.

    This assumes that all child nodes are tokens.
    """
    t = []
    for child in tree.children:
        if isinstance(child, str):
            t.append(child)
        else:
            raise ValueError(f"Expected Token/string but got {child}")
    return "".join(t)


def _to_heading(pos: Pos, root: Tree) -> Heading:
    if root.data != "_heading_start":
        raise ValueError(f"Expected heading start, got {root.data}")
    if len(root.children) != 1:
        raise ValueError(f"Expected exactly one child, got {len(root.children)}")

    tree = root.children[0]
    match tree.data:
        case "title_start":
            text = _text(_child(tree, 0, "title_number"))
            sub_text = _text(_child(tree, 1, "subtitle"))
            return Heading(HeadingType.Title, text, sub_text, pos)
        case "chapter_start":
            text = _text(_child(tree, 0, "chapter_number"))
            sub_text = _text(_child(tree, 1, "subtitle"))
            return Heading(HeadingType.Chapter, text, sub_text, pos)
        case "article_start":
            text = _text(_child(tree, 0, "article_number"))
            sub_text = _text(_child(tree, 1, "subtitle"))
            return Heading(HeadingType.Article, text, sub_text, pos)
        case "section_start":
            text = _text(_child(tree, 0, "section_number"))
            if len(tree.children) > 1:
                sub_text = _text(_child(tree, 1, "section_subtitle"))
            else:
                sub_text = ""
            return Heading(HeadingType.Section, text, sub_text, pos)
        case _:
            raise ValueError(f"Unknown heading type: {tree.type}")


def _child(tree: Tree, idx: int, name: str) -> Tree:
    child_tree = tree.children[idx]
    if child_tree.data != name:
        raise ValueError(f"Expected {name}, got {child_tree.data}")
    return child_tree


def _text(tree: Tree):
    """
    Get all text from the tree's children.

    This assumes that all child nodes are tokens.
    """
    t = []
    for child in tree.children:
        if isinstance(child, str):
            t.append(child)
        else:
            raise ValueError(f"Expected Token/string but got {child}")
    return ''.join(t)
 

heading_grammar = r"""
_heading_start: title_start | chapter_start | article_start | section_start

title_start: _SPAN_M title_number " - " subtitle
chapter_start: _SPAN_M chapter_number " - " subtitle
article_start: _SPAN_M article_number " - " subtitle

!title_number: "TITLE " NAT
!chapter_number: "CHAPTER " NAT
!article_number: "ARTICLE " NAT

subtitle: RAW_UPPER_TEXT _cont_upper_line?
_cont_upper_line: _m_upper_text

!section_number: NAT "-" NAT "-" NAT
section_start: _INDENT _SPAN_M_B section_number "." section_subtitle?
section_subtitle: RAW_TEXT (_LINE _sep{_m_b_text, _LINE})? 

_m_upper_text: _SPAN_M RAW_UPPER_TEXT
_m_b_text: _SPAN_M_B RAW_TEXT

NAT: /[1-9][0-9]*/

RAW_TEXT: /(?:(?!<<)[^\n])+/
RAW_UPPER_TEXT: /(?:(?!<<)[^\na-z])+/

_sep{x, sep}: x (sep x)*

_LINE: /<<LINE [a-zA-Z0-9(), ]+>>/
_INDENT: /<<INDENT>>/

_SPAN_M.2: /<<SPAN_M>>/
_SPAN_M_B.2: /<<SPAN_M_B>>/

EOL: /\n/

%ignore EOL
"""


def find_headers(doc: pymupdf.Document) -> list[Heading]:
    text = "\n".join(pdf_to_token_stream(doc, DEFAULT_OPTIONS))

    lark = Lark(
        heading_grammar,
        start="_heading_start",
        parser="lalr",
        propagate_positions=True,
    )

    headings = []
    text_idx = 0
    while True:
        # find next line
        next_nl_idx = text.find("\n", text_idx+1)
        if next_nl_idx == -1:
            break
        text_idx = next_nl_idx + 1
        parses = find_matches(text[text_idx:], "_heading_start", lark)

        if len(parses) >= 1:
            # get longest possible parse
            parse = parses[-1]
            heading = _to_heading(text_idx, parse)
            headings.append(heading)

    return headings


def to_asciidoc(doc: pymupdf.Document) -> str:
    headers = find_headers(doc)

    adoc = io.StringIO()
    for header in headers:
        level = header.type.value + 1
        adoc.write('=' * level)
        adoc.write(" ")
        adoc.write(header.text)
        adoc.write(" - ")
        adoc.write(header.sub_text)
        adoc.write("\n")

    return adoc.getvalue()

    
def main():
    input_dir = Path(config.STATUTES_DATA_DIR / "wy" / "pdf")

    output_dir = Path(config.STATUTES_DATA_DIR / "wy" / "asciidoc")
    output_dir.mkdir(parents=True, exist_ok=True)

    for filename in input_dir.iterdir():
        if filename.suffix == ".pdf":
            pdf_path = input_dir / filename
            output_path = output_dir / f"{filename.stem}.adoc"
            print(f"{pdf_path} -> {output_path}")

            adoc = to_asciidoc(pymupdf.open(pdf_path))

            with open(output_path, "w") as file:
                file.write(adoc)
