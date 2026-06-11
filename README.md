# ICO Scraper

## Slovenská dokumentácia

### Prehľad

ICO Scraper je FastAPI webová aplikácia na vyhľadávanie slovenských firiem podľa IČO. Získava dáta z verejných zdrojov, rozdeľuje ich do záložiek a umožňuje export do JSON alebo XLSX.

Frontend je v `templates/index.html`, JavaScript v `static/app.js` a štýly v `static/styles.css`. `app.py` je kompatibilitný ASGI wrapper, FastAPI routy sú v `ico_scraper/web.py`, scraping a orchestrácia v `ico_scraper/core.py` a XLSX export v `ico_scraper/exporters/xlsx.py`.

### Funkcie

- Vyhľadávanie podľa IČO.
- Výber zdrojov cez prepínače.
- Samostatné záložky pre ORSR, RPVS, FinStat, RÚZ, CRZ a export dát.
- Záložka `Všeob. Info` iba pri zapnutí všetkých zdrojov.
- Bezpečné spracovanie prázdnych výsledkov.
- Export do `.json` a `.xlsx`.
- Kopírovanie JSON výstupu.
- Parsovanie FinStat grafov do vlastných grafov v UI.
- Experimentálny paralelný režim pre lokálne testovanie výkonu.

### Zdroje dát

| Zdroj | Kľúč | Technológia | Obsah |
| --- | --- | --- | --- |
| ORSR | `orsr` | Selenium | Obchodné meno, sídlo, štatutárny orgán, dozorná rada, akcie, akcionár, právne skutočnosti. |
| RPVS | `rpvs` | Selenium | Register partnerov verejného sektora. |
| FinStat | `finstat` | `requests` + Selenium | Základné údaje, finančné ukazovatele, grafy. |
| RÚZ | `ruz` | Selenium | Účtovné závierky a výročné správy vrátane dokumentov. |
| CRZ | `crz` | `requests` | Prvých 10 zmlúv z Centrálneho registra zmlúv. |

### Štruktúra projektu

```text
.
├── app.py              # Kompatibilitný ASGI wrapper pre uvicorn app:app
├── main.py             # Kompatibilitný CLI wrapper pre python main.py
├── ico_scraper/
│   ├── web.py          # FastAPI routy, statické súbory, exporty
│   ├── browser.py      # Selenium driver a debug helpery
│   ├── core.py         # Scraping, parsovanie portálov, orchestrácia
│   └── exporters/
│       └── xlsx.py     # XLSX export do template.xlsx
├── templates/
│   └── index.html      # HTML UI
├── static/
│   ├── app.js          # JavaScript webového UI
│   └── styles.css      # Štýly webového UI
├── requirements.txt    # Python závislosti
├── apt.txt             # Systémové balíky pre Render
├── Procfile            # Start command pre Render
├── Dockerfile          # Docker image pre web aplikáciu
├── docker-compose.yaml # Selenium Chrome + scraper
├── example.html        # Lokálne HTML príklady pre vývoj parserov
└── README.md           # Dokumentácia
```

### Požiadavky

- Python 3.12 alebo novší.
- Chromium/Chrome a kompatibilný ChromeDriver pre Selenium zdroje.
- Internetové pripojenie.

Python závislosti:

```bash
venv/bin/pip install -r requirements.txt
```

Render systémové balíky sú v `apt.txt`:

```text
chromium
chromium-driver
```

### Lokálne spustenie

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
PORT=8000 venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

Potom otvor:

```text
http://127.0.0.1:8000
```

Ak Selenium nevie spustiť lokálny Chrome/Chromium, zdroje ORSR, RPVS, RÚZ a FinStat grafy môžu zlyhať. CRZ a FinStat základné údaje používajú `requests`.

### Docker Compose

Projekt obsahuje `docker-compose.yaml` so Selenium Chrome kontajnerom:

```bash
docker compose up --build
```

Compose nastavuje:

```text
SELENIUM_URL=http://selenium:4444/wd/hub
```

Tento režim je vhodný hlavne na testovanie Selenium prostredia. Pre bežný webový beh je jednoduchšie použiť `uvicorn`.

### Render deployment

Použi typ služby **Python Web Service**.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Health check path:

```text
/health
```

Ak Selenium nevie nájsť Chromium, nastav:

```text
CHROME_BIN=/path/to/chromium
```

### Environment premenné

| Premenná | Predvolené | Popis |
| --- | --- | --- |
| `PORT` | podľa prostredia | Port webovej aplikácie. |
| `MAX_CONCURRENT_SCRAPES` | `1` | Počet súbežných scrape požiadaviek. |
| `SELENIUM_URL` | prázdne | Remote Selenium server. Ak chýba, použije sa lokálny Chrome. |
| `CHROME_BIN` | prázdne | Cesta ku Chrome/Chromium binárke. |
| `DEBUG_PORTAL_ERRORS` | `0` | Pri `1` vypisuje tracebacky portálových chýb. |
| `PARALLEL_PORTAL_SCRAPES` | `0` | Experimentálny lokálny paralelný režim. |
| `PARALLEL_PORTAL_WORKERS` | automaticky | Počet workerov pre paralelný režim. |
| `FINSTAT_API_KEY` | prázdne | API kľúč pre `finstatapitest.py`. |
| `FINSTAT_PRIVATE_KEY` | prázdne | Privátny API kľúč pre `finstatapitest.py`. |
| `FINSTAT_ICO` | `35757442` | IČO pre test FinStat API. |
| `FINSTAT_ENDPOINT` | `https://www.finstat.sk/api/basic` | Endpoint pre test FinStat API. |
| `FINSTAT_TIMEOUT` | `20` | Timeout testu FinStat API. |
| `FINSTAT_STATION_ID` | prázdne | Voliteľný FinStat API parameter. |
| `FINSTAT_STATION_NAME` | prázdne | Voliteľný FinStat API parameter. |

### Webové rozhranie

UI obsahuje vstup pre IČO, prepínače zdrojov, výsledkové záložky a export dát. `Všeob. Info` sa zobrazí iba vtedy, keď sú zapnuté všetky zdroje. Pri čiastočnom výbere sa zobrazia len vybrané zdroje a export.

### API

#### `GET /`

Vráti webové rozhranie.

#### `GET /health`

Health check.

```bash
curl http://127.0.0.1:8000/health
```

#### `GET /scrape`

Spustí scraping.

| Parameter | Povinný | Popis |
| --- | --- | --- |
| `ico` | áno | Slovenské IČO. |
| `sources` | nie | Čiarkou oddelené zdroje. Ak chýba, použijú sa všetky. |

Príklady:

```bash
curl 'http://127.0.0.1:8000/scrape?ico=36785512'
curl 'http://127.0.0.1:8000/scrape?ico=36785512&sources=orsr,finstat,crz'
```

Možné zdroje:

```text
orsr,rpvs,finstat,ruz,crz
```

#### `POST /export/xlsx`

Vytvorí XLSX zo zaslaného JSON výsledku. Používa ho frontend.

### Výstup

Základný tvar:

```json
{
  "ico": "36785512",
  "orsr": {},
  "rpvs": {},
  "finstat": {},
  "ruz": {},
  "crz": {}
}
```

Ak zdroj nemá dáta alebo zlyhá izolovane:

```json
{
  "message": "Na tomto portáli nie sú informácie o firme."
}
```

### Export

Frontend podporuje stiahnutie `.json`, stiahnutie `.xlsx` a kopírovanie JSON do schránky.

### FinStat grafy

FinStat grafy sa parsujú zo štruktúry Highcharts SVG/HTML, ak je to možné. Podporované sú čiarový graf, skladaný stĺpcový graf a koláčový/donut graf.

Aktuálne názvy grafov:

1. `Zisk`
2. `Tržby`
3. `Celkové Výnosy`
4. `Aktíva`
5. `Pasíva`

Ak sa štruktúrované dáta nepodarí získať, screenshot zostáva fallbackom.

### FinStat API test

`finstatapitest.py` slúži na manuálne otestovanie FinStat API:

```bash
FINSTAT_API_KEY='your_api_key' FINSTAT_PRIVATE_KEY='your_private_key' venv/bin/python finstatapitest.py --ico 35757442
```

Používa hash:

```text
sha256("SomeSalt+{apiKey}+{privateKey}++{ico}+ended")
```

Tento skript nie je zapojený do hlavnej webovej aplikácie.

### Experimentálny paralelný režim

Predvolene sú zdroje spracované sekvenčne. Na lokálne testovanie je možné zapnúť paralelné spracovanie:

```bash
PARALLEL_PORTAL_SCRAPES=1 venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

Voliteľne:

```bash
PARALLEL_PORTAL_SCRAPES=1 PARALLEL_PORTAL_WORKERS=3 venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

Pozor: každý Selenium zdroj môže spustiť vlastný Chrome. Na Render free tier to môže spôsobiť nedostatok pamäte.

### Logovanie

Logy s tagmi `[INFO]`, `[WARN]`, `[ERROR]`, `[SUCCESS]`, `[FATAL]` obsahujú timestamp:

```text
[INFO] 2026-05-26 10:06:22 CRZ: scraping...
```

### Riešenie problémov

#### Selenium/Chrome chyba

Skontroluj inštaláciu Chromium/Chrome a ChromeDriver. Alternatívne použi `SELENIUM_URL` s Docker Compose.

#### DNS chyba

Ak sa objaví napríklad:

```text
Failed to resolve 'finstat.sk'
```

ide o sieťový alebo DNS problém prostredia. Over:

```bash
curl -I https://finstat.sk
```

#### Render je pomalý

Je to očakávané pri Selenium scrapingu na free tieri. Bezpečné optimalizácie sú preskočiť screenshoty pri dostupných grafových dátach, paralelizovať iba zdroje bez browsera, pridať cache a nahradiť pevné `sleep()` cielenými waitmi.

### Vývoj

Pred commitom spusti:

```bash
venv/bin/python -m py_compile app.py main.py ico_scraper/web.py ico_scraper/browser.py ico_scraper/core.py ico_scraper/exporters/xlsx.py finstatapitest.py
```

Ak meníš JavaScript v `static/app.js`, môžeš ho overiť príkazom `node --check static/app.js`.

---

## English Documentation

### Overview

ICO Scraper is a FastAPI web application for looking up Slovak companies by IČO. It collects data from public sources, displays the result in tabs, and supports JSON/XLSX export.

The frontend markup lives in `templates/index.html`, JavaScript in `static/app.js`, and styles in `static/styles.css`. `app.py` is a compatibility ASGI wrapper, FastAPI routes live in `ico_scraper/web.py`, scraping and orchestration live in `ico_scraper/core.py`, and XLSX export lives in `ico_scraper/exporters/xlsx.py`.

### Features

- Company lookup by IČO.
- Source selection with UI toggles.
- Separate tabs for ORSR, RPVS, FinStat, RÚZ, CRZ, and export.
- `Všeob. Info` tab when all sources are selected.
- Graceful handling of empty portal results.
- JSON and XLSX export.
- Copy JSON output.
- FinStat chart parsing into native frontend charts.
- Experimental local parallel scraping mode.

### Data Sources

| Source | Key | Technology | Content |
| --- | --- | --- | --- |
| ORSR | `orsr` | Selenium | Business Register data, statutory body, supervisory board, shares, shareholder, legal facts. |
| RPVS | `rpvs` | Selenium | Register of Public Sector Partners. |
| FinStat | `finstat` | `requests` + Selenium | Basic data, financial indicators, charts. |
| RÚZ | `ruz` | Selenium | Accounting statements and annual reports with documents. |
| CRZ | `crz` | `requests` | First 10 contracts from the Central Register of Contracts. |

### Project Structure

```text
.
├── app.py              # Compatibility ASGI wrapper for uvicorn app:app
├── main.py             # Compatibility CLI wrapper for python main.py
├── ico_scraper/
│   ├── web.py          # FastAPI routes, static files, exports
│   ├── browser.py      # Selenium driver and debug helpers
│   ├── core.py         # Scraping, portal parsers, orchestration
│   └── exporters/
│       └── xlsx.py     # XLSX export using template.xlsx
├── templates/
│   └── index.html      # HTML UI
├── static/
│   ├── app.js          # Web UI JavaScript
│   └── styles.css      # Web UI styles
├── requirements.txt    # Python dependencies
├── apt.txt             # System packages for Render
├── Procfile            # Render start command
├── Dockerfile          # Docker image for the web app
├── docker-compose.yaml # Selenium Chrome + scraper
├── example.html        # Local HTML examples for parser development
└── README.md           # Documentation
```

### Requirements

- Python 3.12 or newer.
- Chromium/Chrome and compatible ChromeDriver for Selenium sources.
- Network access.

Install dependencies:

```bash
venv/bin/pip install -r requirements.txt
```

Render system packages are listed in `apt.txt`:

```text
chromium
chromium-driver
```

### Local Run

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
PORT=8000 venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

If Selenium cannot start local Chrome/Chromium, ORSR, RPVS, RÚZ, and FinStat chart scraping may fail. CRZ and FinStat basic data use `requests`.

### Docker Compose

```bash
docker compose up --build
```

The compose file configures:

```text
SELENIUM_URL=http://selenium:4444/wd/hub
```

This is mainly useful for Selenium environment testing. For normal web usage, local `uvicorn` or Render deployment is simpler.

### Render Deployment

Use a **Python Web Service**.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Health check path:

```text
/health
```

If Selenium cannot find Chromium, set:

```text
CHROME_BIN=/path/to/chromium
```

### Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `PORT` | environment-specific | Web server port. |
| `MAX_CONCURRENT_SCRAPES` | `1` | Concurrent scrape API requests. |
| `SELENIUM_URL` | empty | Remote Selenium server URL. If empty, local Chrome is used. |
| `CHROME_BIN` | empty | Path to Chrome/Chromium binary. |
| `DEBUG_PORTAL_ERRORS` | `0` | If `1`, prints detailed portal tracebacks. |
| `PARALLEL_PORTAL_SCRAPES` | `0` | Experimental local parallel mode. |
| `PARALLEL_PORTAL_WORKERS` | automatic | Worker count for parallel mode. |
| `FINSTAT_API_KEY` | empty | API key for `finstatapitest.py`. |
| `FINSTAT_PRIVATE_KEY` | empty | Private API key for `finstatapitest.py`. |
| `FINSTAT_ICO` | `35757442` | IČO for FinStat API test. |
| `FINSTAT_ENDPOINT` | `https://www.finstat.sk/api/basic` | FinStat API test endpoint. |
| `FINSTAT_TIMEOUT` | `20` | FinStat API test timeout. |
| `FINSTAT_STATION_ID` | empty | Optional FinStat API parameter. |
| `FINSTAT_STATION_NAME` | empty | Optional FinStat API parameter. |

### Web UI

The UI contains IČO input, source toggles, result tabs, and data export. `Všeob. Info` is displayed only when all sources are enabled. If only some sources are selected, the app displays only those source tabs and export.

### API

#### `GET /`

Returns the web UI.

#### `GET /health`

Health check.

```bash
curl http://127.0.0.1:8000/health
```

#### `GET /scrape`

Runs scraping.

| Parameter | Required | Description |
| --- | --- | --- |
| `ico` | yes | Slovak IČO. |
| `sources` | no | Comma-separated sources. If missing, all sources are used. |

Examples:

```bash
curl 'http://127.0.0.1:8000/scrape?ico=36785512'
curl 'http://127.0.0.1:8000/scrape?ico=36785512&sources=orsr,finstat,crz'
```

Allowed source keys:

```text
orsr,rpvs,finstat,ruz,crz
```

#### `POST /export/xlsx`

Creates an XLSX file from posted JSON result data. Used by the frontend.

### Output

Basic response shape:

```json
{
  "ico": "36785512",
  "orsr": {},
  "rpvs": {},
  "finstat": {},
  "ruz": {},
  "crz": {}
}
```

If a source has no data or fails in isolation:

```json
{
  "message": "Na tomto portáli nie sú informácie o firme."
}
```

### Export

The frontend supports `.json` download, `.xlsx` download, and JSON copy to clipboard.

### FinStat Charts

FinStat charts are parsed from Highcharts SVG/HTML where possible. Supported chart types are line chart, stacked bar chart, and pie/donut chart.

Current chart names:

1. `Zisk`
2. `Tržby`
3. `Celkové Výnosy`
4. `Aktíva`
5. `Pasíva`

If structured parsing fails, screenshots remain as fallback.

### FinStat API Test

`finstatapitest.py` manually tests the FinStat API:

```bash
FINSTAT_API_KEY='your_api_key' FINSTAT_PRIVATE_KEY='your_private_key' venv/bin/python finstatapitest.py --ico 35757442
```

It signs requests with:

```text
sha256("SomeSalt+{apiKey}+{privateKey}++{ico}+ended")
```

This script is not connected to the main web app.

### Experimental Parallel Mode

By default, sources are processed sequentially. To test parallel scraping locally:

```bash
PARALLEL_PORTAL_SCRAPES=1 venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

Optional worker count:

```bash
PARALLEL_PORTAL_SCRAPES=1 PARALLEL_PORTAL_WORKERS=3 venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

Warning: every Selenium source may start its own Chrome instance. This can exhaust memory on Render free tier.

### Logging

Logs beginning with `[INFO]`, `[WARN]`, `[ERROR]`, `[SUCCESS]`, or `[FATAL]` include a timestamp:

```text
[INFO] 2026-05-26 10:06:22 CRZ: scraping...
```

### Troubleshooting

#### Selenium/Chrome error

Check Chromium/Chrome and ChromeDriver installation. Alternatively use `SELENIUM_URL` with Docker Compose.

#### DNS error

If you see:

```text
Failed to resolve 'finstat.sk'
```

it is a network or DNS issue in the runtime environment. Check:

```bash
curl -I https://finstat.sk
```

#### Render is slow

This is expected with Selenium scraping on the free tier. Safer optimizations are skipping screenshots when chart data is available, parallelizing only non-browser sources, adding caching, and replacing fixed `sleep()` calls with targeted waits.

### Development

Before committing, run:

```bash
venv/bin/python -m py_compile app.py main.py ico_scraper/web.py ico_scraper/browser.py ico_scraper/core.py ico_scraper/exporters/xlsx.py finstatapitest.py
```

If you change JavaScript in `static/app.js`, run `node --check static/app.js`.
