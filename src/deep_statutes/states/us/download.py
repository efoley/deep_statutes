import logging
import tempfile
import os
from pathlib import Path
import zipfile

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from deep_statutes.config import STATUTES_DATA_DIR


logging.basicConfig(
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# def download_pdfs(output_dir: Path):
#     # URL of the page to scrape
#     url = "https://uscode.house.gov/download/download.shtml"

#     # Fetch the page content
#     response = requests.get(url)
#     response.raise_for_status()  # Raise an error for bad responses
#     soup = BeautifulSoup(response.text, "html.parser")

#     pdf_as = soup.select('div.uscitemlist a[href*="pdf"]')
#     pdf_urls = [urljoin(url, a["href"]) for a in pdf_as]

#     # Ensure the output directory exists
#     output_dir.mkdir(parents=True, exist_ok=True)

#     logger.info(f"Found {len(pdf_urls)} PDF links.")

#     # Download each PDF
#     for url in pdf_urls:
#         output_path = output_dir / Path(urlparse(url).path).name
#         logger.info(f"Downloading {url} to {output_path}")
#         pdf_response = requests.get(url)
#         pdf_response.raise_for_status()
#         with open(output_path, "wb") as f:
#             f.write(pdf_response.content)


def download_pdfs_from_all_zip(output_dir: Path):
    url = "https://uscode.house.gov/download/releasepoints/us/pl/119/4/pdf_uscAll@119-4.zip"

    # download the zip file
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad responses


    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(response.content)

        with zipfile.ZipFile(temp_file.name, "r") as zip_ref:
            zip_ref.extractall(output_dir)


def main():
    output_dir = Path(STATUTES_DATA_DIR) / "us" / "pdf"
    download_pdfs_from_all_zip(output_dir)
