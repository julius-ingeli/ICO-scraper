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

    .summary-layout {
      display: grid;
      gap: 22px;
    }

    .mock-chart {
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      padding: 16px;
      background: #f8fafc;
    }

    .mock-chart-title {
      margin: 0 0 14px;
      font-size: 16px;
      line-height: 1.3;
      color: #1f2933;
    }

    .chart-bars {
      height: 220px;
      display: grid;
      grid-template-columns: repeat(4, minmax(54px, 1fr));
      align-items: end;
      gap: 14px;
      padding: 14px 8px 10px;
      border-left: 1px solid #cbd2d9;
      border-bottom: 1px solid #cbd2d9;
      background: linear-gradient(to top, rgba(203, 210, 217, 0.32) 1px, transparent 1px);
      background-size: 100% 44px;
    }

    .chart-bar-group {
      min-width: 0;
      display: grid;
      gap: 8px;
      justify-items: center;
    }

    .chart-bar {
      width: min(42px, 100%);
      min-height: 12px;
      border-radius: 5px 5px 0 0;
      background: #0f766e;
    }

    .chart-bar.loss { background: #b42318; }

    .chart-label {
      color: #52606d;
      font-size: 12px;
      font-weight: 700;
    }

    .chart-disclaimer {
      margin: 12px 0 0;
      color: #7c4a03;
      font-size: 13px;
      line-height: 1.45;
    }

    .notice {
      padding: 14px 16px;
      border: 1px solid #f0c36d;
      border-radius: 6px;
      background: #fff8e6;
      color: #7c4a03;
      font-size: 14px;
      line-height: 1.45;
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

    .raw-json-wrap {
      position: relative;
    }

    .copy-button {
      position: absolute;
      top: 10px;
      right: 10px;
      z-index: 1;
      width: 38px;
      height: 38px;
      display: inline-grid;
      place-items: center;
      border: 1px solid #4b5563;
      border-radius: 6px;
      padding: 0;
      background: #1f2937;
      color: #e5e7eb;
      cursor: pointer;
    }

    .copy-button:hover,
    .copy-button:focus-visible {
      border-color: #99f6e4;
      color: #99f6e4;
      outline: none;
    }

    .copy-button.copied {
      border-color: #99f6e4;
      background: #134e4a;
      color: #ccfbf1;
    }

    .copy-button svg {
      width: 18px;
      height: 18px;
      stroke: currentColor;
      stroke-width: 2;
      fill: none;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .raw-json {
      margin: 0;
      min-height: 420px;
      overflow: auto;
      border-radius: 8px;
      background: #111827;
      color: #e5e7eb;
      padding: 58px 18px 18px;
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
      .chart-bars { grid-template-columns: repeat(2, minmax(54px, 1fr)); }
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
    let latestRawJson = '';

    const copyIcon = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect>
        <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path>
      </svg>
    `;

    const checkIcon = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M20 6 9 17l-5-5"></path>
      </svg>
    `;

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

      if (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 1 && value.message) {
        return `<div class="notice">${renderValue(value.message)}</div>`;
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


    function firstValue(...values) {
      for (const value of values) {
        if (value !== null && value !== undefined && String(value).trim() !== '') {
          return value;
        }
      }
      return '-';
    }

    function renderSummary(data) {
      const orsr = data.orsr || {};
      const finstatBasic = data.finstat?.zakladne_udaje || {};
      const companyName = firstValue(orsr.obchodne_meno, finstatBasic['Obchodné meno'], finstatBasic.Názov);
      const address = firstValue(orsr.sidlo, finstatBasic['Sídlo'], finstatBasic.Adresa);
      const foundingDay = firstValue(orsr.den_zapisu, finstatBasic['Dátum vzniku']);

      return `
        <section class="summary-layout">
          <div class="field-grid">
            <div class="field-label">IČO</div>
            <div class="field-value">${renderValue(data.ico)}</div>
            <div class="field-label">Názov spoločnosti</div>
            <div class="field-value">${renderValue(companyName)}</div>
            <div class="field-label">Adresa</div>
            <div class="field-value">${renderValue(address)}</div>
            <div class="field-label">Deň vzniku</div>
            <div class="field-value">${renderValue(foundingDay)}</div>
          </div>
          ${renderMockChart()}
        </section>
      `;
    }

    function renderMockChart() {
      const bars = [
        { label: '2021', height: 48, type: 'profit' },
        { label: '2022', height: 72, type: 'profit' },
        { label: '2023', height: 34, type: 'loss' },
        { label: '2024', height: 86, type: 'profit' }
      ];

      return `
        <section class="mock-chart" aria-label="Maketa finančného grafu">
          <h3 class="mock-chart-title">Zisk / strata</h3>
          <div class="chart-bars">
            ${bars.map(bar => `
              <div class="chart-bar-group">
                <div class="chart-bar ${bar.type === 'loss' ? 'loss' : ''}" style="height: ${bar.height}%"></div>
                <div class="chart-label">${bar.label}</div>
              </div>
            `).join('')}
          </div>
          <p class="chart-disclaimer">Tento graf nereprezentuje reálne dáta, je to iba maketa.</p>
        </section>
      `;
    }

    async function copyText(text) {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return;
      }

      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      textarea.remove();
    }

    function bindCopyButton() {
      const copyButton = document.querySelector('#copy-raw');
      if (!copyButton) return;

      copyButton.addEventListener('click', async () => {
        try {
          await copyText(latestRawJson);
          copyButton.classList.add('copied');
          copyButton.innerHTML = checkIcon;
          copyButton.title = 'Skopírované';
          copyButton.setAttribute('aria-label', 'Skopírované');
          setTimeout(() => {
            copyButton.classList.remove('copied');
            copyButton.innerHTML = copyIcon;
            copyButton.title = 'Kopírovať JSON';
            copyButton.setAttribute('aria-label', 'Kopírovať JSON');
          }, 1600);
        } catch (error) {
          statusEl.className = 'status error';
          statusEl.textContent = 'Kopírovanie zlyhalo.';
        }
      });
    }

    function renderPanel(key, value, active) {
      if (key === 'raw') {
        const rawJson = JSON.stringify(value, null, 2);
        return `
          <section class="panel ${active ? 'active' : ''}" id="panel-${key}" role="tabpanel">
            <h2 class="panel-title">Raw JSON</h2>
            <div class="raw-json-wrap">
              <button class="copy-button" id="copy-raw" type="button" title="Kopírovať JSON" aria-label="Kopírovať JSON">
                ${copyIcon}
              </button>
              <pre class="raw-json">${renderValue(rawJson)}</pre>
            </div>
          </section>
        `;
      }

      if (key === 'ico') {
        return `
          <section class="panel ${active ? 'active' : ''}" id="panel-${key}" role="tabpanel">
            <h2 class="panel-title">${formatKey(key)}</h2>
            ${renderSummary(value)}
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
      latestRawJson = JSON.stringify(data, null, 2);
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
        const value = key === 'raw' || key === 'ico' ? data : data[key];
        return renderPanel(key, value, index === 0);
      }).join('');

      tabs.querySelectorAll('.tab-button').forEach(tab => {
        tab.addEventListener('click', () => activateTab(tab.dataset.tab));
      });
      bindCopyButton();
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
