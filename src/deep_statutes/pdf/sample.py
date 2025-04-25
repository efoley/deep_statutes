import argparse
import math
from pathlib import Path

import numpy as np
import pymupdf


class PDFSampler:
    def __init__(
        self,
        percent: float,
        min_num_pages: int,
        min_fragment_num_pages: int,
        always_include_first_page: bool,
        random_seed: int = 8675309,
    ):
        self.frac = percent / 100.0
        self.min_num_pages = min_num_pages
        self.min_fragment_num_pages = min_fragment_num_pages
        self.always_include_first_page = always_include_first_page
        self.random_seed = random_seed
        self.gen = np.random.default_rng(random_seed)

    def _choose_page_indices(self, num_pages: int) -> list[int]:
        min_num_start_pages = int(
            math.ceil(self.min_num_pages / self.min_fragment_num_pages)
        )
        num_start_pages = max(
            min_num_start_pages,
            int(math.ceil(num_pages * self.frac / self.min_fragment_num_pages)),
        )

        if self.always_include_first_page:
            num_start_pages = max(num_start_pages - 1, 0)
            start_pages = [0]
        else:
            start_pages = []

        start_pages += self.gen.choice(
            num_pages - self.min_fragment_num_pages, num_start_pages, replace=False
        ).tolist()

        start_pages.sort()
        pages = []
        for i in range(num_start_pages):
            start = start_pages[i]
            end = min(start + self.min_fragment_num_pages, num_pages)
            pages.extend(range(start, end))
        pages = list(set(pages))
        pages.sort()
        return pages

    def sample_subset(self, input_doc: pymupdf.Document, output_doc: pymupdf.Document):
        page_idxs = self._choose_page_indices(len(input_doc))

        for k, idx in enumerate(page_idxs):
            if k == len(page_idxs) - 1:
                final = 1
            else:
                final = 0
            output_doc.insert_pdf(input_doc, from_page=idx, to_page=idx, final=final)


def main():
    description = """
    Subset a directory of PDF files to a single PDF file for use in determining the structure and
    hierarchy of a set of PDF documents.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "input_paths",
        nargs="+",
        type=str,
    )
    parser.add_argument(
        "--output_pdf",
        "-o",
        required=True,
        type=str,
    )

    parser.add_argument(
        "--percent",
        type=float,
        default=2.0,
        help="Specify the percentage of pages (default 1%) to include in the subset.",
    )

    parser.add_argument(
        "--min_num_pages_per_pdf",
        type=int,
        default=10,
        help="Minimum number of pages from each PDF to include in the subset.",
    )

    parser.add_argument(
        "--min_fragment_num_pages",
        type=int,
        default=5,
        help="Minimum number of consecutive pages to include if possible.",
    )

    parser.add_argument(
        "--always_include_first_page",
        action="store_true",
        help="Always include the first page of each PDF in the subset.",
        default=True,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=8675309,
        help="Random seed for reproducibility.",
    )

    args = parser.parse_args()

    sampler = PDFSampler(
        percent=args.percent,
        min_num_pages=args.min_num_pages_per_pdf,
        min_fragment_num_pages=args.min_fragment_num_pages,
        always_include_first_page=args.always_include_first_page,
        random_seed=args.seed,
    )

    output_doc = pymupdf.open()

    input_paths = [Path(p) for p in args.input_paths]
    input_paths = sorted(input_paths, key=lambda x: x.stem)

    for pdf_path in input_paths:
        input_doc = pymupdf.open(pdf_path)
        sampler.sample_subset(input_doc, output_doc)

    output_doc.save(args.output_pdf)
