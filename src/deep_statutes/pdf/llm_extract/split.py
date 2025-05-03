import argparse
import io
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
import pymupdf

from .toc import llm_parse_toc, DocumentTOC, Header

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HeaderTreeNode(BaseModel):
    header: Header
    parent: Optional["HeaderTreeNode"]
    children: list["HeaderTreeNode"] = []
    page_range: tuple[int, int]  # 1-indexed and inclusive

    def num_pages(self) -> int:
        return self.page_range[1] - self.page_range[0] + 1


def _build_header_tree(toc: DocumentTOC, num_pages: int) -> HeaderTreeNode:
    """
    Build a tree of headers from the TOC.
    """
    # TODO EDF not a big deal if this isn't true, but if so it is kind of weird and
    # we need a "doc" level header
    assert toc.headers[0].page == 1
    root = HeaderTreeNode(header=toc.headers[0], parent=None, page_range=[1, num_pages])
    path: list[HeaderTreeNode] = [root]
    for header in toc.headers[1:]:
        level = toc.hierarchy_level(header.type)
        while toc.hierarchy_level(path[-1].header.type) >= level:
            # this could happen if there isn't a toc entry for "this entire document"
            # we could deal with that if it occurs by always putting in a header at "document" level
            # or something
            assert len(path) > 1

            path[-1].page_range = (path[-1].page_range[0], header.page)
            path.pop()
        node = HeaderTreeNode(
            header=header, parent=path[-1], page_range=[header.page, num_pages]
        )
        path[-1].children.append(node)
        path.append(node)
    return root


def _choose_split_headers(
    toc: DocumentTOC, num_pages: int, max_num_pages_hint: int
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
    if len(toc.headers) == 0:
        raise ValueError("No headers found in the TOC.")

    root = _build_header_tree(toc, num_pages)

    # now traverse to find split headers
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


def _get_path(node: HeaderTreeNode) -> str:
    """
    Get the path of the header in the tree.
    """
    path = []
    while node is not None:
        path.append(node.header.text.replace(" ", "_"))
        node = node.parent
    return "-".join(reversed(path))


def split_pdf(pdf_path: Path, toc: DocumentTOC, output_dir: Path):
    doc = pymupdf.open(pdf_path)
    num_pages = len(doc)
    split_headers = _choose_split_headers(toc, num_pages, max_num_pages_hint=16)

    for header in split_headers:
        header_path = _get_path(header)
        page_start, page_end = header.page_range

        output_path = output_dir / f"{header_path}.pdf"
        logger.info(f"Writing pages {page_start}-{page_end} {output_path}.")

        output_doc = pymupdf.open()
        output_doc.insert_pdf(
            doc,
            from_page=page_start - 1,
            to_page=page_end - 1, 
            final=1
        )
        output_doc.save(output_path)


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

    toc = llm_parse_toc(pdf_path)

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

    with open(args.output_dir / "toc.md", "w") as f:
        f.write(md.getvalue())

    split_pdf(pdf_path, toc, args.output_dir)
