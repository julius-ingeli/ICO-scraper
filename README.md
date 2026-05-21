# ICO-scraper

A small FastAPI web app for scraping Slovak company data by IČO and returning the result as JSON.

## Local run

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
PORT=8000 venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`.

## Render

Use a Python Web Service.

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

`apt.txt` installs Chromium packages for Selenium on Render. If Chromium is installed in a non-standard location, set `CHROME_BIN` in Render environment variables.

## API

```text
GET /scrape?ico=36785512
```

Returns the scraped subject data as JSON.
