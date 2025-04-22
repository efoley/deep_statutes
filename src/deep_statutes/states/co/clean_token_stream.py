from pathlib import Path

from lark import Lark

from deep_statutes.lark.util import find_matches


footer_grammar = r"""
footer: _crs2024 _uncert _page
_crs2024: _LINE _SPAN_M "Colorado Revised Statutes 2024"
_uncert: _LINE _INDENT* _SPAN_M "Uncertified Printout"
_page: _LINE _INDENT* _SPAN_M /Page\s+[1-9][0-9]*\s+of\s+[1-9][0-9]*/

_LINE: /<<LINE [a-zA-Z0-9(), ]+>>/
_INDENT: /<<INDENT>>/

_SPAN_M: /<<SPAN_M>>/

EOL: /\n/

%ignore EOL
"""


def clean_token_stream(in_path: Path, out_path: Path) -> None:
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
