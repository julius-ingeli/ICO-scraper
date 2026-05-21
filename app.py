import asyncio
import os
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from main import scrape_subject


app = FastAPI(title="ICO Scraper", version="1.0.0")
_scrape_limit = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_SCRAPES", "1")))


INDEX_HTML = """<!doctype html>
<html lang="sk">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ICO Scraper</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4f6f8;
      color: #1f2933;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: stretch;
      justify-content: center;
      padding: 32px;
    }

    main {
      width: min(1080px, 100%);
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 18px;
    }

    .topbar {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 24px;
    }

    h1 {
      margin: 0 0 6px;
      font-size: 32px;
      line-height: 1.1;
      font-weight: 700;
    }

    p {
      margin: 0;
      color: #52606d;
      font-size: 15px;
    }

    form {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }

    label {
      font-size: 14px;
      font-weight: 650;
      color: #323f4b;
    }

    input {
      width: 180px;
      height: 42px;
      border: 1px solid #cbd2d9;
      border-radius: 6px;
      padding: 0 12px;
      font-size: 16px;
      background: white;
      color: #1f2933;
    }

    button {
      height: 42px;
      border: 0;
      border-radius: 6px;
      padding: 0 16px;
      font-size: 15px;
      font-weight: 700;
      background: #0f766e;
      color: white;
      cursor: pointer;
    }

    button:disabled {
      cursor: progress;
      opacity: 0.68;
    }

    .status {
      min-height: 22px;
      font-size: 14px;
      color: #52606d;
    }

    .status.error { color: #b42318; }

    pre {
      margin: 0;
      width: 100%;
      min-height: 420px;
      overflow: auto;
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      background: #111827;
      color: #e5e7eb;
      padding: 18px;
      font-size: 13px;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
    }

    @media (max-width: 720px) {
      body { padding: 18px; }
      .topbar { align-items: stretch; flex-direction: column; }
      h1 { font-size: 26px; }
      form { align-items: stretch; }
      label { width: 100%; }
      input, button { width: 100%; }
    }
  </style>
</head>
<body>
  <main>
    <section class="topbar">
      <div>
        <h1>ICO Scraper</h1>
        <p>Zadajte IČO a aplikácia vráti dostupné údaje vo formáte JSON.</p>
      </div>
      <form id="scrape-form">
        <label for="ico">IČO</label>
        <input id="ico" name="ico" inputmode="numeric" autocomplete="off" pattern="[0-9]{8}" maxlength="8" placeholder="36785512" required />
        <button id="submit" type="submit">Vyhľadať</button>
      </form>
    </section>
    <div class="status" id="status"></div>
    <pre id="output">{}</pre>
  </main>

  <script>
    const form = document.querySelector('#scrape-form');
    const input = document.querySelector('#ico');
    const button = document.querySelector('#submit');
    const statusEl = document.querySelector('#status');
    const output = document.querySelector('#output');

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const ico = input.value.trim();
      statusEl.className = 'status';
      statusEl.textContent = 'Spracúvam požiadavku...';
      button.disabled = true;
      output.textContent = '{}';

      try {
        const response = await fetch(`/scrape?ico=${encodeURIComponent(ico)}`);
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || 'Požiadavka zlyhala.');
        }
        output.textContent = JSON.stringify(data, null, 2);
        statusEl.textContent = 'Hotovo.';
      } catch (error) {
        statusEl.className = 'status error';
        statusEl.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


def normalize_ico(ico: str) -> str:
    normalized = re.sub(r"\s+", "", ico)
    if not re.fullmatch(r"\d{8}", normalized):
        raise HTTPException(status_code=400, detail="IČO musí obsahovať presne 8 číslic.")
    return normalized


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/scrape")
async def scrape(ico: str = Query(..., description="Slovak company IČO")) -> dict:
    normalized_ico = normalize_ico(ico)

    async with _scrape_limit:
        try:
            return await run_in_threadpool(scrape_subject, normalized_ico)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Scraping zlyhal: {type(exc).__name__}: {exc}") from exc
