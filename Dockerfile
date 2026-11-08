  FROM python:3.13-slim

  WORKDIR /app

  RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium \
      chromium-driver \
      fonts-liberation \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

  ENV CHROME_BIN=/usr/bin/chromium
  ENV PYTHONUNBUFFERED=1

  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  COPY . .

  EXPOSE 8000

  CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]