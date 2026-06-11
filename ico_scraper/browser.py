import builtins
import os
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


SELENIUM_URL = os.getenv("SELENIUM_URL")
_original_print = builtins.print


def print(*args, **kwargs):
    if args and isinstance(args[0], str):
        match = re.match(r"^(\[(?:DEBUG|INFO|WARN|ERROR|SUCCESS|FATAL)\])\s*(.*)$", args[0])
        if match:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            args = (f"{match.group(1)} {timestamp} {match.group(2)}", *args[1:])
    return _original_print(*args, **kwargs)


def create_driver(max_attempts=10, delay=3):
    options = Options()

    # workaround na privacy error
    options.set_capability("acceptInsecureCerts", True)
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1365,900")

    chrome_bin = os.getenv("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin

    if not SELENIUM_URL:
        print("[INFO] Spúšťam lokálny headless Chrome/Chromium.")
        return webdriver.Chrome(options=options)

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[INFO] Pokus {attempt}/{max_attempts} o pripojenie na Selenium: {SELENIUM_URL}")
            driver = webdriver.Remote(
                command_executor=SELENIUM_URL,
                options=options
            )
            print("[INFO] Selenium session vytvorená úspešne.")
            return driver
        except Exception as e:
            print(f"[WARN] Selenium ešte nie je ready: {e}")
            if attempt == max_attempts:
                raise
            time.sleep(delay)


def save_debug(driver, prefix="debug"):
    try:
        with open(f"{prefix}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.save_screenshot(f"{prefix}.png")
        print(f"[INFO] Uložené {prefix}.html a {prefix}.png")
    except Exception as e:
        print("[WARN] Nepodarilo sa uložiť debug artefakty:", e)
