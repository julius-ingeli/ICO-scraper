"""Compatibility entrypoint for ASGI servers.

The FastAPI application lives in ico_scraper.web. Keeping this wrapper
preserves existing commands such as `uvicorn app:app`.
"""

from ico_scraper.web import app

__all__ = ["app"]
