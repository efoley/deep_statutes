import argparse
import io
import logging
from concurrent import futures
from pathlib import Path

import pymupdf

from deep_statutes import config
from deep_statutes.pdf.split import split_pdf
from deep_statutes.pdf.toc import DocumentTOC, HeaderTreeNode
from deep_statutes.states.co.token_stream import write_clean_token_stream
from deep_statutes.pdf.parse import find_headers

logger = logging.getLogger(__name__)

HEADER_GRAMMAR = r"""
_header_start: title_start | article_start | part_start | section_start

title_start: _SPAN_L title_number _LINE+ title_subtitle
article_start: _SPAN_M_B article_number _LINE+ article_subtitle
part_start: _SPAN_M part_number _LINE+ part_subtitle

title_subtitle: _subtitle_upper
article_subtitle: _subtitle
part_subtitle: _subtitle_upper

_subtitle_upper_line: _INDENT* _m_upper_text
_subtitle_upper: _sep{_subtitle_upper_line, LINE}

_subtitle_line: _INDENT* _m_text
_subtitle: _sep{_subtitle_line, LINE}

!title_number: "TITLE " NAT
!article_number: "ARTICLE " (NAT | NAT1)
!part_number: "PART " (NAT | NAT1)

!section_number: NAT "-" NAT "-" (NAT | NAT1)
section_start: _INDENT _SPAN_M_B section_number "." section_subtitle?
section_subtitle: RAW_TEXT (LINE _sep{_m_b_text, LINE})? 

_m_upper_text: _SPAN_M RAW_UPPER_TEXT
_m_b_text: _SPAN_M_B RAW_TEXT
_m_text: _SPAN_M RAW_TEXT

NAT: /[1-9][0-9]*/
NAT1: /[1-9][0-9]*\.[0-9]+/

RAW_TEXT: /(?:(?!<<)[^\n])+/
RAW_UPPER_TEXT: /(?:(?!<<)[^\na-z])+/

_sep{x, sep}: x (sep x)*

LINE: /<<LINE [a-zA-Z0-9(), ]+>>/
_LINE: /<<LINE [a-zA-Z0-9(), ]+>>/
_INDENT: /<<INDENT>>/

_SPAN_L: /<<SPAN_L>>/
_SPAN_L_B: /<<SPAN_L_B>>/
_SPAN_M: /<<SPAN_M>>/
_SPAN_M_B: /<<SPAN_M_B>>/

EOL: /\n/

%ignore EOL
"""

HEADER_TYPES = ["title", "article", "part", "section"]


def parse_toc(token_stream_path: Path) -> DocumentTOC:
    toc = find_headers(
        header_grammar=HEADER_GRAMMAR,
        header_types=HEADER_TYPES,
        token_stream_path=token_stream_path,
    )

    return toc


def _write_toc_md(
    header_tree: HeaderTreeNode,
    split_headers_paths: list[tuple[HeaderTreeNode, str]],
    out_md_path: Path,
) -> None:
    md = io.StringIO()

    # write the header tree to markdown
    # note that the hierarchy level here is determined by the position in the tree
    # and not by the header type
    frontier = [(1, header_tree)]
    while len(frontier) > 0:
        level, node = frontier.pop()
        frontier += [(level + 1, child) for child in reversed(node.children)]

        text = node.header.text
        sub_text = node.header.sub_text

        md.write(f"{'#' * level} {text} ({sub_text})\n")
        md.write("\n")

    with open(out_md_path, "w") as f:
        f.write(md.getvalue())


def _process_pdf(
    pdf_path: Path,
    token_stream_path: Path,
    split_pdf_dir: Path,
    max_num_pages_hint: int = 16,
) -> None:
    filename = pdf_path.stem
    # skip constitution for now
    if filename.endswith("-00"):
        return

    doc = pymupdf.open(pdf_path)

    write_clean_token_stream(
        doc,
        token_stream_path,
    )

    toc = parse_toc(token_stream_path)
    header_tree = HeaderTreeNode.from_toc(toc, num_pages=len(doc))

    header_to_path = split_pdf(
        doc,
        header_tree,
        split_pdf_dir,
        max_num_pages_hint=max_num_pages_hint,
    )

    _write_toc_md(
        header_tree,
        header_to_path,
        split_pdf_dir / f"{filename}.md",
    )

    with open(
        split_pdf_dir / f"{filename}_headers.json",
        "w",
    ) as f:
        f.write(header_tree.model_dump_json(indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Split Colorado statutes PDF into smaller PDFs and generate ToC."
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "-j",
        "--num_jobs",
        type=int,
        default=4,
        help="Number of parallel jobs to run.",
    )
    parser.add_argument(
        "-p",
        "--max_num_pages_hint",
        type=int,
        default=16,
        help="Maximum number of pages to include in each split PDF. Note that this is a hint and may be ignored if the split header is too large.",
    )
    args = parser.parse_args()

    input_dir = Path(config.STATUTES_DATA_DIR / "co" / "pdf")
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_token_stream_dir = Path(output_dir / "token_stream")
    pdf_token_stream_dir.mkdir(parents=True, exist_ok=True)

    split_pdf_root_dir = Path(output_dir / "split")
    split_pdf_root_dir.mkdir(parents=True, exist_ok=True)

    input_paths = sorted(
        input_dir.glob("crs2024-title-*.pdf"),
        key=lambda x: x.stem,
    )

    process_pdf_args = []
    for pdf_path in input_paths:
        split_pdf_dir = split_pdf_root_dir / pdf_path.stem
        split_pdf_dir.mkdir(parents=True, exist_ok=True)

        process_pdf_args.append(
            (
                pdf_path,
                pdf_token_stream_dir / f"{pdf_path.stem}.txt",
                split_pdf_dir,
                args.max_num_pages_hint,
            )
        )

    if args.num_jobs == 1:
        for proc_args in process_pdf_args:
            logger.info(f"Processing {proc_args[0]}")
            _process_pdf(*proc_args)
    else:
        with futures.ProcessPoolExecutor(max_workers=args.num_jobs) as executor:
            res = executor.map(
                _process_pdf,
                *zip(*process_pdf_args),
            )

        # we iterate through res to force the execution of the futures
        for _ in res:
            pass
