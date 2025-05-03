import os
from pathlib import Path

STATUTES_DATA_DIR=Path(os.environ.get('STATUTES_DATA_DIR', '/Users/eric/Development/deep_statutes_data'))

GEMINI_API_KEY=os.environ.get('GEMINI_API_KEY')