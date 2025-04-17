## some utilities
from dataclasses import dataclass
from typing import Iterator, Sequence, TypedDict

import pymupdf


Pos = Sequence[int]  # a hierarchical position (slowest idx first)

BBox = tuple[float, float, float, float]


class SpanDict(TypedDict):
    size: float  # font size
    font: str  # font name
    text: str
    bbox: BBox


class LineDict(TypedDict):
    spans: list[SpanDict]
    wmode: int
    dir: tuple[float, float]
    bbox: BBox


class BlockDict(TypedDict):
    type: int  # 0 is text; 1 is image
    lines: list[LineDict]
    bbox: BBox


def iter_blocks(page: pymupdf.Page) -> Iterator[tuple[Pos, BlockDict]]:
    d = page.get_text("dict")
    blocks = d["blocks"]
    for block_idx, block in enumerate(blocks):
        yield (block_idx,), block


def iter_lines(page: pymupdf.Page) -> Iterator[tuple[Pos, LineDict]]:
    d = page.get_text("dict")
    blocks = d["blocks"]
    for block_idx, block in enumerate(blocks):
        for line_idx, line in enumerate(block["lines"]):
            yield (block_idx, line_idx), line


def iter_spans(page: pymupdf.Page) -> Iterator[tuple[Pos, SpanDict]]:
    d = page.get_text("dict")
    blocks = d["blocks"]
    for block_idx, block in enumerate(blocks):
        for line_idx, line in enumerate(block["lines"]):
            for span_idx, span in enumerate(line["spans"]):
                yield (block_idx, line_idx, span_idx), span


def is_bbox_centered(bbox: BBox, page_width: float, pct_tol=5.0, max_pct_width=60.) -> bool:
    x1, y1, x2, y2 = bbox
    if x2 - x1 >= max_pct_width/100. * page_width:
        return False
    center_x = (x1 + x2) / 2
    pt_tol = page_width * pct_tol / 100.0
    return abs(center_x - page_width / 2) < pt_tol


def get_bbox_indent_level(bbox: BBox, left_margin: float, indent_size: float) -> int:
    x1 = bbox[0]
    return int(round((x1 - left_margin) / indent_size))

def get_line_margins(page: pymupdf.Page) -> list[tuple[float, float]]:
    line_margins = []
    for _, line in iter_lines(page):
        margin = (None, None)
        for span_idx, span in enumerate(line["spans"]):
            x0, _, x1, _ = span["bbox"]
            if margin[0] is None or x0 < margin[0]:
                margin = (x0, margin[1])
            if margin[1] is None or x1 > margin[1]:
                margin = (margin[0], x1)
        line_margins.append(margin)
    return line_margins


def cluster(vals: list[float], tol=1.0) -> list[float]:
    """
    Cluster values with some tolerance.
    """
    if tol != 1.0:
        # TODO EDF
        raise NotImplementedError("Only tolerance 1. is supported.")

    return list(set(round(v) for v in vals))


def unique_line_heights(page: pymupdf.Page, tol=1.0) -> list[float]:
    heights = []
    for _, line in iter_lines(page):
        height = line["bbox"][3] - line["bbox"][1]
        assert height >= 0.0
        heights.append(height)

    return cluster(heights, tol)


def unique_fonts(page: pymupdf.Page) -> list[str]:
    """ """
    fonts = []
    for _, span in iter_spans(page):
        font_name = span["font"]
        font_size = round(span["size"], 1)
        fonts.append(f"{font_name} {font_size}")
    return list(set(fonts))


def page_margins(page: pymupdf.Page) -> tuple[float, float]:
    line_margins = []
    for _, line in iter_lines(page):
        margin = (None, None)
        for span_idx, span in enumerate(line["spans"]):
            x0, _, x1, _ = span["bbox"]
            if margin[0] is None or x0 < margin[0]:
                margin = (x0, margin[1])
            if margin[1] is None or x1 > margin[1]:
                margin = (margin[0], x1)
        line_margins.append(margin)

    # get min left margin and max right margin
    min_left_margin = min(line_margins, key=lambda x: x[0])[0]
    max_right_margin = max(line_margins, key=lambda x: x[1])[1]

    return min_left_margin, max_right_margin


def unique_left_align(page: pymupdf.Page) -> list[int]:
    """
    Return a list of unique x coordinates for left-aligned lines.
    """
    d = page.get_text("dict")
    page_width = d["width"]
    xs = []
    for _, line in iter_lines(page):
        if is_bbox_centered(line["bbox"], page_width):
            continue
        x0, _, x1, _ = line["bbox"]
        xs.append(x0)

    return cluster(xs, 1)


def summarize_page(page: pymupdf.Page):
    margin = page_margins(page)
    line_heights = unique_line_heights(page)
    fonts = unique_fonts(page)
    left_aligns = unique_left_align(page)

    print("Page:")
    print(f"  Min Left Margin: {margin[0]}")
    print(f"  Left Aligns: {left_aligns}")
    print(f"  Line Heights: {line_heights}")
    print(f"  Fonts: {fonts}")
    print()


def summarize_doc(doc: pymupdf.Document):
    fonts = []
    left_aligns = []
    line_heights = []
    for page in doc:
        fonts += unique_fonts(page)
        left_aligns += unique_left_align(page)
        line_heights += unique_line_heights(page)
    fonts = list(set(fonts))
    left_aligns = list(set(left_aligns))
    line_heights = list(set(line_heights))

    print("Doc:")
    print(f"  Left Aligns: {left_aligns}")
    print(f"  Line Heights: {line_heights}")
    print(f"  Fonts: {fonts}")
    print()


def is_pathological(doc: pymupdf.Document) -> bool:
    """
    Check if the document has anything that we probably can't handle yet.
    """
    pathological = False
    if doc.is_reflowable:
        pathological = True
        print("Document is reflowable, which we don't support yet.")
    for page_idx, page in enumerate(doc):
        # check that page has no images or annotations
        if (
            len(page.get_images()) > 0
            or len(page.annots()) > 0
            or len(page.widgets()) > 0
        ):
            pathological = True
            print(f"Page {page.number} has images or annotations.")
        # check that lines are in correct order and non-overlapping
        prev_line = None
        for _, line in iter_lines(page):
            if prev_line is not None and line["bbox"][1] < prev_line["bbox"][3]:
                pathological = True
                print(
                    f"Page {page_idx} has lines that are out of order or overlapping."
                )
            prev_line = line

    return pathological
