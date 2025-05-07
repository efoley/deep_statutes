from pathlib import Path

from lark import Lark, Tree

from deep_statutes.lark import find_matches
from deep_statutes.pdf.toc import DocumentTOC, Header


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
    return " ".join(t).strip()


def _to_header(
    page: int, text_range: tuple[int, int], header_types: list[str], root: Tree
) -> Header:
    if root.data != "_header_start":
        raise ValueError(f'Expected "_header_start", got {root.data}')
    if len(root.children) != 1:
        raise ValueError(f"Expected exactly one child, got {len(root.children)}")

    tree = root.children[0]

    if not tree.data.endswith("_start"):
        raise ValueError(
            f'Expected grammar rule ending in "_start", got grammar rule "{tree.data}"'
        )

    header_type = tree.data[:-6]  # remove "_start"
    if header_type not in header_types:
        raise ValueError(
            f'Header type "{header_type}" not in header types "{header_types}"'
        )

    text = _text(_child(tree, 0, f"{header_type}_number"))

    if len(tree.children) > 1:
        sub_text = _text(_child(tree, 1, f"{header_type}_subtitle"))
    else:
        sub_text = ""

    return Header(
        type=header_type,
        text=text,
        sub_text=sub_text,
        page=page,
    )


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


example_grammar_not_valid = r"""
_header_start: title_start | article_start | part_start | section_start

title_start: _SPAN_L title_name _LINE+ title_subtitle
article_start: _SPAN_M_B article_name _LINE+ article_subtitle
part_start: _SPAN_M part_name _LINE+ part_subtitle

EOL: /\n/

%ignore EOL
"""

header_grammar_guidelines = """
There should be a rule for each header type, and the rule should be named
<name>_start. 

The rule should contain a child rule named <name>_number, which is the title for the header.
The rule should optionally contain a child rule named <name>_subtitle, which is the subtitle for the header.
"""


def find_headers(
    header_grammar: str, header_types: list[str], token_stream_path: Path
) -> DocumentTOC:
    """
    Given a grammar with a "_header_start" rule containing a nested rule for each
    header type, find all headers in the token stream.

    Args:
        header_grammar (str): The lark grammar (must be LALR) to use for parsing the headers.
        header_types (list[str]): The list of header types to find, in hierarchical order.
        token_stream_path (Path): The path to the token stream file.
    """
    lark = Lark(
        header_grammar,
        start="_header_start",
        parser="lalr",
        propagate_positions=True,
    )

    headers = []
    text_idx = 0
    with open(token_stream_path, "r") as file:
        text = file.read()

    # keep track of the current page from the token stream
    page = 0
    while True:
        # find next line
        next_nl_idx = text.find("\n", text_idx + 1)
        if next_nl_idx == -1:
            break
        text_idx = next_nl_idx + 1

        if text[text_idx:].startswith("<<PAGE "):
            close = text.find(">>", text_idx)
            page = int(text[text_idx + 7 : close])

        parses, end_pos = find_matches(text[text_idx:], "_header_start", lark)

        if len(parses) >= 1:
            # get longest possible parse
            parse = parses[-1]
            e = end_pos[-1]
            header = _to_header(page, (text_idx, text_idx + e + 1), header_types, parse)
            headers.append(header)

    return DocumentTOC(header_types=header_types, headers=headers)
