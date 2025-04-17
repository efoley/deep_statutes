import requests
from pathlib import Path
import time

from deep_statutes.config import STATUTES_DATA_DIR

# Base URL structure
BASE_URL = "https://wyoleg.gov/statutes/compress/"
# Directory to save files
OUTPUT_DIR = "raw_pdf"


def download_pdfs(out_dir: Path):
    print("Starting download attempt...")

    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Downloading Loop ---
    # Loop through numbers 1 to 99
    for i in range(1, 100):
        # Format the number with a leading zero if needed (e.g., 01, 02, ..., 09, 10, ...)
        number_str = f"{i:02d}"
        filename = f"title{number_str}.pdf"
        url = f"{BASE_URL}{filename}"
        output_path = out_dir / filename

        print(f"Attempting to download: {url}")

        try:
            # Make the request. Allow redirects (-L in curl). stream=True is efficient for downloads.
            # Add a timeout to prevent hanging indefinitely.
            # Consider adding a User-Agent header as some sites block default script agents.
            headers = {
                "User-Agent": "Python Downloader Script (compatible; example-bot/1.0)"
            }
            response = requests.get(
                url, stream=True, allow_redirects=True, timeout=30, headers=headers
            )

            # Check if the request was successful (status code 2xx).
            # raise_for_status() will raise an HTTPError for bad responses (4xx or 5xx).
            # This replicates the behavior of curl's -f flag.
            response.raise_for_status()

            # Write the content to the file in binary mode
            with open(output_path, "wb") as f:
                # Download in chunks to handle potentially large files
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Successfully downloaded: {filename}")

        except requests.exceptions.HTTPError as e:
            # This catches errors raised by raise_for_status() (like 404 Not Found)
            # The shell script specifically checked for exit code 22, often meaning 4xx/5xx with -f.
            # We can be more specific by checking the status code if needed.
            status_code = e.response.status_code
            print(
                f"Skipped: {filename} (HTTP Error: {status_code} - {e.response.reason})"
            )
            # Note: Unlike curl -f -O, this approach typically won't create an empty file on 404,
            # because we only open the file *after* a successful status check.

        except requests.exceptions.RequestException as e:
            # Catches other potential issues like connection errors, timeouts, etc.
            # This corresponds to other non-zero exit codes from curl.
            print(f"Skipped: {filename} (Error downloading: {e})")

        # Optional: Add a small delay between requests to be polite to the server
        time.sleep(3)

    print("Download process finished.")


def main():
    download_pdfs(STATUTES_DATA_DIR / "wy" / "pdf")


if __name__ == "__main__":
    main()
