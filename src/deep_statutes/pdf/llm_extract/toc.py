import logging
from pathlib import Path

from google import genai
from google.genai import types
import pdfplumber
from pydantic import BaseModel

from deep_statutes.config import GEMINI_API_KEY


logger = logging.getLogger(__name__)


MODEL_FLASH = "gemini-2.5-flash-preview-04-17"


class Header(BaseModel):
    type: str
    text: str
    sub_text: str
    page: int # 1-indexed


class DocumentTOC(BaseModel):
    header_types: list[str]
    headers: list[Header]

    def hierarchy_level(self, header_type: str) -> int:
        """
        Get the hierarchy level of a header type according to the document's order.

        This may not actually be the order in the document since sometimes headers skip levels, but
        it gives us a hint as to how to structure a tree representing the ToC.
        """
        return self.header_types.index(header_type)


TOC_PROMPT = """\n\n
This document is a PDF of laws. It contains text with a specific structure, e.g a hierarchy like:
`Title`
`Article`
`Part`
`Section` (labeled like `1-10-24`).

Your task is to determine the names of headers that appear in this document (e.g. `Title`, `Chapter`, `Article`, etc.) 
and extract the table of contents from this document. The table of contents does not need to list sections; just go down to
the level above section level.

The table of contents should be returned as a JSON object structured as follows:
{
    "header_types": ["title", "article", "part"],
    "headers": [
        {
            "type": "title",
            "text": "TITLE 1",
            "sub_text": "GENERAL PROVISIONS",
            "page": 1
        },
        {
            "type": "article",
            "text": "ARTICLE 1",
            "sub_text": "Property Ceded to United States",
            "page": 2
        },
        {
            "type": "part",
            "text": "PART 1",
            "sub_text": "PROFESSIONS AND OCCUPATIONS",
            "page": 3
        }
    ]
}

The "type" field should be one of the header type names that appears in the document (e.g. "title", "article", "part"), in order
of hierarchy.
The "text" field should contain the text of the header (e.g. "TITLE 3").
The "sub_text" field should contain the descriptive text that usually follows the header (e.g. "PROFESSIONS AND OCCUPATIONS".)
The "page" field should contain the page number where the header is found (the first page is page 1.)
"""


def _query_toc_from_gemini(pdf_path: Path) -> types.GenerateContentResponse:
    client = genai.Client(api_key=GEMINI_API_KEY)
    gem_pdf_file = client.files.upload(file=pdf_path)


    config = types.GenerateContentConfig(
        response_mime_type='application/json',
        response_schema=DocumentTOC,
        thinking_config=types.ThinkingConfig(
            thinking_budget=0,
        ),
    )

    response = client.models.generate_content(
        model=MODEL_FLASH,
        contents=[
            gem_pdf_file,
            TOC_PROMPT,
        ],
        config=config,
    )

    return response



def _check_headers_present(pdf_path: Path, toc: DocumentTOC) -> list[str]:
    """
    Check if the headers in the TOC are present in the PDF.
    
    Returns:
        list[str]: A list of headers that were not found in the PDF.
    """
    not_found = []
    with pdfplumber.open(pdf_path) as pdf:
        for header in toc.headers:
            found = False
            page = pdf.pages[header.page - 1]  # page numbers are 1-indexed in the TOC
            text = page.extract_text(layout=False)
            found = header.text in text
            if not found:
                # this may not be an error, e.g. footer text could be mixed in with the header text,
                # but generate a warning so we can investigate
                logger.info(f"Header '{header.text}' not found on PDF page {header.page}.")
                not_found.append(header.text)
    return not_found


def llm_parse_toc(pdf_path: Path) -> DocumentTOC:
    toc_response = _query_toc_from_gemini(pdf_path)

    logger.info("Found hierarchy: " + ", ".join(toc_response.parsed.header_types))

    if (not_found := _check_headers_present(pdf_path, toc_response.parsed)) :
        logger.warning("Headers in TOC not found in PDF. Please check the PDF for accuracy.")
        logger.warning("\tMissing headers: " + ", ".join(not_found))

    toc = toc_response.parsed

    cleaned_headers = []
    missing_header_types = set()
    for header in toc.headers:
        if header.type not in toc.header_types:
            missing_header_types.add(header.type)
            logger.info(f"Skipping header {header} of type '{header.type}' not in header types.")
            continue

        cleaned_header = Header(
            type=header.type,
            text=header.text.strip().replace("\n", " "),
            sub_text=header.sub_text.strip().replace("\n", " "),
            page=header.page,
        )
        cleaned_headers.append(cleaned_header)

    if len(missing_header_types) > 0:
        logger.warning(f"Header types '{', '.join(missing_header_types)}' not found in hierarchy.")

    return DocumentTOC(
        header_types=toc.header_types,
        headers=cleaned_headers,
    )
