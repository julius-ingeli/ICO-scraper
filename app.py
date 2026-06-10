import asyncio
import importlib.util
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from main import AVAILABLE_SOURCES, scrape_subject


BASE_DIR = Path(__file__).resolve().parent
INDEX_TEMPLATE = BASE_DIR / "templates" / "index.html"
STATIC_DIR = BASE_DIR / "static"


def load_xlsx_exporter():
    module_path = BASE_DIR / "xslx-export.py"
    spec = importlib.util.spec_from_file_location("xslx_export", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nepodarilo sa načítať exporter: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


xlsx_exporter = load_xlsx_exporter()

app = FastAPI(title="ICO Scraper", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
_scrape_limit = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_SCRAPES", "1")))


def normalize_ico(ico: str) -> str:
    normalized = re.sub(r"\s+", "", ico)
    if not re.fullmatch(r"\d{8}", normalized):
        raise HTTPException(status_code=400, detail="IČO musí obsahovať presne 8 číslic.")
    return normalized


def normalize_sources(sources: str | None) -> set[str]:
    if not sources:
        return set(AVAILABLE_SOURCES)

    selected = {source.strip().lower() for source in sources.split(",") if source.strip()}
    invalid = selected - AVAILABLE_SOURCES
    if invalid:
        raise HTTPException(status_code=400, detail=f"Neplatné zdroje: {', '.join(sorted(invalid))}.")
    if not selected:
        raise HTTPException(status_code=400, detail="Vyberte aspoň jeden zdroj informácií.")
    return selected


@app.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    return FileResponse(INDEX_TEMPLATE, media_type="text/html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/export/xlsx")
async def export_xlsx(request: Request) -> StreamingResponse:
    try:
        data = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Neplatné JSON dáta pre export.") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Export očakáva JSON objekt.")

    output, filename = await run_in_threadpool(xlsx_exporter.build_template_xlsx, data)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/scrape")
async def scrape(
    ico: str = Query(..., description="Slovak company IČO"),
    sources: str | None = Query(None, description="Comma-separated source keys"),
    crz_omit_legal_form: bool = Query(False, description="Remove legal-form suffixes from CRZ supplier-name searches"),
) -> dict:
    normalized_ico = normalize_ico(ico)
    selected_sources = normalize_sources(sources)

    async with _scrape_limit:
        try:
            return await run_in_threadpool(
                scrape_subject,
                normalized_ico,
                selected_sources,
                crz_omit_legal_form=crz_omit_legal_form,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Scraping zlyhal: {type(exc).__name__}: {exc}") from exc
