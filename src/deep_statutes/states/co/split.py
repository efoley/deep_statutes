import argparse
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
_subtitle_upper: _sep{_subtitle_upper_line, _LINE}

_subtitle_line: _INDENT* _m_text
_subtitle: _sep{_subtitle_line, _LINE}

!title_number: "TITLE " NAT
!article_number: "ARTICLE " (NAT | NAT1)
!part_number: "PART " (NAT | NAT1)

!section_number: NAT "-" NAT "-" NAT
section_start: _INDENT _SPAN_M_B section_number "." section_subtitle?
section_subtitle: RAW_TEXT (_LINE _sep{_m_b_text, _LINE})? 

_m_upper_text: _SPAN_M RAW_UPPER_TEXT
_m_b_text: _SPAN_M_B RAW_TEXT
_m_text: _SPAN_M RAW_TEXT

NAT: /[1-9][0-9]*/
NAT1: /[1-9][0-9]*\.[0-9]+/

RAW_TEXT: /(?:(?!<<)[^\n])+/
RAW_UPPER_TEXT: /(?:(?!<<)[^\na-z])+/

_sep{x, sep}: x (sep x)*

_LINE: /<<LINE [a-zA-Z0-9(), ]+>>/
_INDENT: /<<INDENT>>/

_SPAN_L: /<<SPAN_L>>/
_SPAN_L_B: /<<SPAN_L_B>>/
_SPAN_M: /<<SPAN_M>>/
_SPAN_M_B: /<<SPAN_M_B>>/

EOL: /\n/

%ignore EOL
"""


def parse_toc(token_stream_path: Path) -> DocumentTOC:
    toc = find_headers(
        header_grammar=HEADER_GRAMMAR,
        header_types=["title", "article", "part", "section"],
        token_stream_path=token_stream_path,
    )

    return toc


def _process_pdf(
    pdf_path: Path,
    token_stream_path: Path,
    split_pdf_dir: Path,
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
    )

    # TODO EDF write header_to_path to json


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

