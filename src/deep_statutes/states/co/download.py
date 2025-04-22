import os
import sys
import requests
from pathlib import Path

from deep_statutes.config import STATUTES_DATA_DIR

# Base URL for the PDF files
BASE_URL = "https://leg.colorado.gov/sites/default/files/images/olls/"


def main():
    # Construct the full output directory path
    # Using pathlib is generally more robust for path manipulation
    out_dir = Path(STATUTES_DATA_DIR) / "co" / "pdf"

    # Create the output directory if it doesn't exist (including parent dirs)
    out_dir.mkdir(parents=True, exist_ok=True)
   
    files_to_download = []
    for i in range(45):
        file_name = f"crs2024-title-{str(i).zfill(2)}.pdf"
        files_to_download.append(f"{BASE_URL}{file_name}")

    files_to_download.append(f"{BASE_URL}crs2024-index.pdf")

    # Use a requests session for potential connection reuse
    with requests.Session() as session:
        for url in files_to_download:
            try:
                # Extract filename from URL
                file_name = url.split('/')[-1]
                output_path = out_dir / file_name

                print(f"Downloading: {url} -> {output_path}")

                # Make the GET request, stream=True is good practice for large files
                response = session.get(url, stream=True, timeout=30) # Added timeout

                # Check if the request was successful (status code 2xx)
                response.raise_for_status()

                # Write the content to the file in chunks
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192): # 8KB chunks
                        f.write(chunk)

                print(f"Successfully downloaded: {file_name}")

            except requests.exceptions.RequestException as e:
                print(f"Error downloading {url}: {e}", file=sys.stderr)
            except OSError as e:
                print(f"Error writing file {output_path}: {e}", file=sys.stderr)
            except Exception as e:
                # Catch any other unexpected errors
                print(f"An unexpected error occurred for {url}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()