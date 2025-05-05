import argparse
import io
import logging
from pathlib import Path

import pymupdf

from deep_statutes.pdf.toc import DocumentTOC, HeaderTreeNode
from deep_statutes.pdf.llm_extract.gemini_toc import parse_toc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _choose_split_headers(
    root: HeaderTreeNode, max_num_pages_hint: int
) -> list[HeaderTreeNode]:
    """
    Choose the headers to split the PDF on.

    We want to split the document in a way that respects the hierarchy of the document.
    In particular, we try to split such that the page length between headers is not longer
    than the max_num_pages_hint.

    Args:
        toc (DocumentTOC): The table of contents of the document.
        num_pages (int): The number of pages in the document.
        max_num_pages_hint (int): The maximum number of pages between headers; will be exceeded
            if the lowest level header is too long.
    Returns:
        list[HeaderTreeNode]: The headers to split on.
    """
    # traverse the tree and find the headers to split on
    splits = []
    frontier = [root]
    while len(frontier) > 0:
        node = frontier.pop()

        if node.num_pages() > max_num_pages_hint:
            frontier += node.children
        else:
            # split the document here; no need to go deeper
            splits.append(node)

    return splits


def split_pdf(
    doc: pymupdf.Document, header_tree: HeaderTreeNode, output_dir: Path
) -> dict[str, HeaderTreeNode]:
    split_headers = _choose_split_headers(header_tree, max_num_pages_hint=16)

    header_to_path = {}

    for header in split_headers:
        header_path = "-".join([h.header.text for h in header.path()])
        page_start, page_end = header.page_range

        header_to_path[header_path] = header

        output_path = output_dir / f"{header_path}.pdf"
        logger.info(f"Writing pages {page_start}-{page_end} {output_path}.")

        output_doc = pymupdf.open()
        output_doc.insert_pdf(
            doc, from_page=page_start - 1, to_page=page_end - 1, final=1
        )
        output_doc.save(output_path)

    return header_to_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate ToC and split PDF using Gemini."
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to the PDF file.",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=Path,
        help="Directory to save the split PDFs and ToC.",
    )
    args = parser.parse_args()

    pdf_path = args.pdf_path

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if not args.output_dir.exists():
        args.output_dir.mkdir(parents=True, exist_ok=True)

    toc = parse_toc(pdf_path)

    if len(toc.headers) == 0:
        raise ValueError("No headers found in the TOC.")

    doc = pymupdf.open(pdf_path)
    root = HeaderTreeNode.from_toc(toc, len(doc))

    header_type_level = {h: i + 1 for i, h in enumerate(toc.header_types)}

    md = io.StringIO()
    md.write("---\n")
    md.write(f"Generated from {pdf_path}\n")
    md.write("Inferred header types are: " + ", ".join(toc.header_types) + "\n")
    md.write("---\n\n")
    for header in toc.headers:
        level = header_type_level[header.type]
        md.write(
            f"{'#' * level} {header.text} - {header.sub_text} (Page {header.page})\n\n"
        )

    toc_name = pdf_path.stem + "_toc.md"
    with open(args.output_dir / toc_name, "w") as f:
        f.write(md.getvalue())

    split_pdf(doc, root, args.output_dir)
