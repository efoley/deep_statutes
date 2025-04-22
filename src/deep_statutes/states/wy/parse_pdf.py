import io
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from lark import Lark, Tree

from deep_statutes.lark import find_matches


class HeaderType(Enum):
    Title = auto()
    Chapter = auto()
    Article = auto()
    Section = auto()


@dataclass
class Header:
    type: HeaderType
    text: str
    sub_text: str
    text_range: tuple[int, int]


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


def _to_header(text_range: tuple[int, int], root: Tree) -> Header:
    if root.data != "_header_start":
        raise ValueError(f'Expected "_header_start", got {root.data}')
    if len(root.children) != 1:
        raise ValueError(f"Expected exactly one child, got {len(root.children)}")

    tree = root.children[0]
    match tree.data:
        case "title_start":
            text = _text(_child(tree, 0, "title_number"))
            sub_text = _text(_child(tree, 1, "subtitle"))
            return Header(HeaderType.Title, text, sub_text, text_range)
        case "chapter_start":
            text = _text(_child(tree, 0, "chapter_number"))
            sub_text = _text(_child(tree, 1, "subtitle"))
            return Header(HeaderType.Chapter, text, sub_text, text_range)
        case "article_start":
            text = _text(_child(tree, 0, "article_number"))
            sub_text = _text(_child(tree, 1, "subtitle"))
            return Header(HeaderType.Article, text, sub_text, text_range)
        case "section_start":
            text = _text(_child(tree, 0, "section_number"))
            if len(tree.children) > 1:
                sub_text = _text(_child(tree, 1, "section_subtitle"))
            else:
                sub_text = ""
            return Header(HeaderType.Section, text, sub_text, text_range)
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
 

header_grammar = r"""
_header_start: title_start | chapter_start | article_start | section_start

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


def find_headers(token_stream_path: Path) -> list[Header]:
    lark = Lark(
        header_grammar,
        start="_header_start",
        parser="lalr",
        propagate_positions=True,
    )

    headings = []
    text_idx = 0
    with open(token_stream_path, "r") as file:
        text = file.read()

    while True:
        # find next line
        next_nl_idx = text.find("\n", text_idx+1)
        if next_nl_idx == -1:
            break
        text_idx = next_nl_idx + 1
        parses, end_pos = find_matches(text[text_idx:], "_header_start", lark)

        if len(parses) >= 1:
            # get longest possible parse
            parse = parses[-1]
            e = end_pos[-1]
            heading = _to_header((text_idx, text_idx+e+1), parse)
            headings.append(heading)

    return headings

