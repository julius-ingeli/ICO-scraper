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
      justify-content: center;
      padding: 32px;
    }

    main {
      width: min(1120px, 100%);
      display: grid;
      grid-template-rows: auto auto 1fr;
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

    .tabs {
      display: none;
      gap: 8px;
      align-items: center;
      overflow-x: auto;
      padding-bottom: 2px;
      border-bottom: 1px solid #d9e2ec;
    }

    .tabs.visible { display: flex; }

    .tab-button {
      flex: 0 0 auto;
      height: 38px;
      border: 1px solid #cbd2d9;
      border-bottom: 0;
      border-radius: 6px 6px 0 0;
      padding: 0 14px;
      background: #e4e7eb;
      color: #323f4b;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
    }

    .tab-button.active {
      background: white;
      color: #0f766e;
      border-color: #9fb3c8;
    }

    .results {
      min-height: 420px;
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      background: white;
      overflow: hidden;
    }

    .empty-state {
      min-height: 420px;
      display: grid;
      place-items: center;
      padding: 28px;
      color: #52606d;
      text-align: center;
    }

    .panel {
      display: none;
      padding: 20px;
    }

    .panel.active { display: block; }

    .panel-title {
      margin: 0 0 16px;
      font-size: 22px;
      line-height: 1.25;
      color: #1f2933;
    }

    .field-grid {
      display: grid;
      grid-template-columns: minmax(180px, 280px) minmax(0, 1fr);
      gap: 0;
      border-top: 1px solid #edf1f5;
    }

    .field-label,
    .field-value {
      padding: 12px 10px;
      border-bottom: 1px solid #edf1f5;
      font-size: 14px;
      line-height: 1.45;
    }

    .field-label {
      color: #52606d;
      font-weight: 700;
    }

    .field-value {
      color: #1f2933;
      overflow-wrap: anywhere;
    }

    .nested {
      margin: 4px 0 0;
      padding-left: 14px;
      border-left: 3px solid #d9e2ec;
    }

    .list {
      display: grid;
      gap: 10px;
    }

    .list-item {
      padding: 12px;
      border: 1px solid #d9e2ec;
      border-radius: 6px;
      background: #f8fafc;
    }

    .list-item-title {
      margin: 0 0 8px;
      color: #52606d;
      font-size: 13px;
      font-weight: 700;
    }

    .raw-json {
      margin: 0;
      min-height: 420px;
      overflow: auto;
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
      .field-grid { grid-template-columns: 1fr; }
      .field-label { padding-bottom: 2px; border-bottom: 0; }
      .field-value { padding-top: 2px; }
    }
  </style>
</head>
<body>
  <main>
    <section class="topbar">
      <div>
        <h1>ICO Scraper</h1>
        <p>Zadajte IČO a aplikácia rozdelí výsledok podľa zdroja.</p>
      </div>
      <form id="scrape-form">
        <label for="ico">IČO</label>
        <input id="ico" name="ico" inputmode="numeric" autocomplete="off" pattern="[0-9]{8}" maxlength="8" placeholder="36785512" required />
        <button id="submit" type="submit">Vyhľadať</button>
      </form>
    </section>
    <div class="status" id="status"></div>
    <nav class="tabs" id="tabs" aria-label="Kategórie výsledku"></nav>
    <section class="results" id="results">
      <div class="empty-state">Výsledky sa zobrazia po vyhľadaní IČO.</div>
    </section>
  </main>

  <script>
    const form = document.querySelector('#scrape-form');
    const input = document.querySelector('#ico');
    const button = document.querySelector('#submit');
    const statusEl = document.querySelector('#status');
    const tabs = document.querySelector('#tabs');
    const results = document.querySelector('#results');

    const categoryLabels = {
      ico: 'IČO',
      orsr: 'ORSR',
      rpvs: 'RPVS',
      finstat: 'FinStat',
      ruz: 'RÚZ',
      raw: 'Raw JSON'
    };

    function formatKey(key) {
      return categoryLabels[key] || key
        .replaceAll('_', ' ')
        .replace(/\\b\\w/g, letter => letter.toUpperCase());
    }

    function clearResults(message = 'Výsledky sa zobrazia po vyhľadaní IČO.') {
      tabs.className = 'tabs';
      tabs.innerHTML = '';
      results.innerHTML = `<div class="empty-state">${message}</div>`;
    }

    function renderValue(value) {
      if (value === null || value === undefined || value === '') {
        return '<span>-</span>';
      }

      if (Array.isArray(value)) {
        if (value.length === 0) return '<span>-</span>';
        return `<div class="list">${value.map((item, index) => `
          <div class="list-item">
            <div class="list-item-title">Položka ${index + 1}</div>
            ${renderValue(item)}
          </div>
        `).join('')}</div>`;
      }

      if (typeof value === 'object') {
        const entries = Object.entries(value);
        if (entries.length === 0) return '<span>-</span>';
        return `<div class="field-grid nested">${entries.map(([key, child]) => `
          <div class="field-label">${formatKey(key)}</div>
          <div class="field-value">${renderValue(child)}</div>
        `).join('')}</div>`;
      }

      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    }

    function renderPanel(key, value, active) {
      if (key === 'raw') {
        return `
          <section class="panel ${active ? 'active' : ''}" id="panel-${key}" role="tabpanel">
            <h2 class="panel-title">Raw JSON</h2>
            <pre class="raw-json">${renderValue(JSON.stringify(value, null, 2))}</pre>
          </section>
        `;
      }

      return `
        <section class="panel ${active ? 'active' : ''}" id="panel-${key}" role="tabpanel">
          <h2 class="panel-title">${formatKey(key)}</h2>
          ${renderValue(value)}
        </section>
      `;
    }

    function activateTab(key) {
      document.querySelectorAll('.tab-button').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === key);
        tab.setAttribute('aria-selected', tab.dataset.tab === key ? 'true' : 'false');
      });
      document.querySelectorAll('.panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === `panel-${key}`);
      });
    }

    function renderResults(data) {
      const preferredOrder = ['ico', 'orsr', 'rpvs', 'finstat', 'ruz'];
      const keys = preferredOrder.filter(key => key in data);
      Object.keys(data).forEach(key => {
        if (!keys.includes(key)) keys.push(key);
      });
      keys.push('raw');

      tabs.className = 'tabs visible';
      tabs.innerHTML = keys.map((key, index) => `
        <button class="tab-button ${index === 0 ? 'active' : ''}" type="button" data-tab="${key}" aria-controls="panel-${key}" aria-selected="${index === 0 ? 'true' : 'false'}">
          ${formatKey(key)}
        </button>
      `).join('');

      results.innerHTML = keys.map((key, index) => {
        const value = key === 'raw' ? data : data[key];
        return renderPanel(key, value, index === 0);
      }).join('');

      tabs.querySelectorAll('.tab-button').forEach(tab => {
        tab.addEventListener('click', () => activateTab(tab.dataset.tab));
      });
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const ico = input.value.trim();
      statusEl.className = 'status';
      statusEl.textContent = 'Spracúvam požiadavku...';
      button.disabled = true;
      clearResults('Čakám na výsledok zo zdrojov...');

      try {
        const response = await fetch(`/scrape?ico=${encodeURIComponent(ico)}`);
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || 'Požiadavka zlyhala.');
        }
        renderResults(data);
        statusEl.textContent = 'Hotovo.';
      } catch (error) {
        statusEl.className = 'status error';
        statusEl.textContent = error.message;
        clearResults('Výsledok sa nepodarilo načítať.');
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
