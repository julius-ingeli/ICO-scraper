"""Compatibility CLI wrapper for the scraper package.

The scraping implementation lives in ico_scraper.core. Keeping this wrapper
preserves existing commands such as `python main.py` and imports from `main`.
"""

from ico_scraper.core import *  # noqa: F401,F403
from ico_scraper.core import main as _main


if __name__ == "__main__":
    _main()
