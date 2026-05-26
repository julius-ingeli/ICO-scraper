import os
import sys
import time
import json
import traceback
import re
import builtins
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import urllib3

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ORSR_URL = "https://www.orsr.sk/search_ico.asp"
RPVS_URL = "https://rpvs.gov.sk/rpvs"
RUZ_URL = "https://www.registeruz.sk/cruz-public/domain/accountingentity/simplesearch"
CRZ_URL = "https://www.crz.gov.sk/2171273-sk/centralny-register-zmluv/"

SELENIUM_URL = os.getenv("SELENIUM_URL")


# ============================================================
# HELPERS
# ============================================================

_original_print = builtins.print


def print(*args, **kwargs):
    if args and isinstance(args[0], str):
        match = re.match(r"^(\[(?:INFO|WARN|ERROR|SUCCESS|FATAL)\])\s*(.*)$", args[0])
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


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compact_statutory_person(lines: list[str]) -> list[str]:
    if not lines:
        return []

    # ak je to len typ orgánu alebo príliš krátky záznam, vráť ako je
    if len(lines) < 4:
        return lines

    result = []

    # 1. Meno + funkcia
    first_line = " ".join(lines[:4]).strip()
    result.append(normalize_text(first_line))

    # 2. Adresa: ulica + číslo, mesto + PSČ
    address_parts = []
    if len(lines) >= 6:
        address_parts.append(normalize_text(f"{lines[4]} {lines[5]}"))
    if len(lines) >= 8:
        address_parts.append(normalize_text(f"{lines[6]} {lines[7]}"))
    if address_parts:
        result.append(", ".join(address_parts))

    # 3. Vznik funkcie + (od: ...)
    if len(lines) >= 10:
        function_line = f"{lines[8]} {lines[9]}"
        result.append(normalize_text(function_line))
    elif len(lines) >= 9:
        result.append(normalize_text(lines[8]))

    # ak by bolo riadkov viac než 10, pridaj zvyšok
    if len(lines) > 10:
        for extra in lines[10:]:
            result.append(normalize_text(extra))

    return result

def parse_orsr_section_by_label(soup: BeautifulSoup, section_label: str) -> list:
    """
    Nájde ORSR sekciu podľa labelu v span.tl, napr.:
    - Štatutárny orgán
    - Dozorná rada
    - Akcie
    - Akcionár
    - Ďalšie právne skutočnosti

    Vráti zoznam blokov (každý blok = list riadkov).
    """
    label = None
    for span in soup.select("span.tl"):
        text = span.get_text(" ", strip=True)
        if section_label in text:
            label = span
            break

    if not label:
        return []

    row = label.find_parent("tr")
    if not row:
        return []

    cells = row.find_all("td", recursive=False)
    if len(cells) < 2:
        return []

    content_cell = cells[1]

    # ak sú vnorené tabuľky, ber ich po blokoch
    nested_tables = content_cell.find_all("table", recursive=False)

    results = []

    if nested_tables:
        for tbl in nested_tables:
            text = tbl.get_text("\n", strip=True)
            lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
            if lines:
                results.append(lines)
    else:
        # fallback: sekcia môže byť aj len textovo bez nested tables
        text = content_cell.get_text("\n", strip=True)
        lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
        if lines:
            results.append(lines)

    return results


def compact_raw_section(section_rows: list[list[str]]) -> list[list[str]]:
    cleaned_rows = []

    for row in section_rows:
        cleaned = [
            normalize_text(item.replace("\r", " ").replace("\n", " "))
            for item in row
            if normalize_text(item.replace("\r", " ").replace("\n", " "))
        ]
        cleaned_rows.append(cleaned)

    return cleaned_rows


def compact_akcie_section(section_rows: list[list[str]]) -> list[list[str]]:
    compacted_rows = []

    for row in section_rows:
        cleaned = [normalize_text(item) for item in row if normalize_text(item)]
        compacted = []
        index = 0
        while index < len(cleaned):
            current = cleaned[index]
            next_value = cleaned[index + 1] if index + 1 < len(cleaned) else ""
            if current.startswith("Menovitá hodnota") and next_value == "EUR":
                compacted.append(normalize_text(f"{current} {next_value}"))
                index += 2
                continue
            compacted.append(current)
            index += 1
        compacted_rows.append(compacted)

    return compacted_rows

def clean_value(text: str) -> str:
    if not text:
        return text

    # odstráň copy hlášku
    text = text.replace("Údaj bol úspešne skopírovaný", "")

    # odstráň whitespace znaky
    text = text.replace("\n", " ").replace("\t", " ")

    # zjednoť medzery
    text = " ".join(text.split())

    return text.strip()



# ============================================================
# ORSR
# ============================================================

def find_orsr_ico_input(driver):
    driver.switch_to.default_content()

    elems = driver.find_elements(By.NAME, "ICO")
    if elems:
        return elems[0]

    frames = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")

    for frame in frames:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            elems = driver.find_elements(By.NAME, "ICO")
            if elems:
                return elems[0]
        except Exception:
            continue

    driver.switch_to.default_content()
    return None


def orsr_search_company(driver, wait, ico: str):
    print("[INFO] ORSR: otváram stránku...")
    driver.get(ORSR_URL)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

    search_input = find_orsr_ico_input(driver)
    if not search_input:
        raise RuntimeError("ORSR: Nenašiel som input[name='ICO'].")

    search_input.clear()
    search_input.send_keys(ico)

    search_button = wait.until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//input[@type='submit' and contains(normalize-space(@value), 'Hľadaj')]"
        ))
    )

    print("[INFO] ORSR: klikám na Hľadaj...")
    driver.execute_script("arguments[0].click();", search_button)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")


def orsr_open_first_result(driver, wait):
    first_result_xpath = "//tbody/tr[td][1]/td[2]//a[contains(@href, 'vypis.asp')]"

    print("[INFO] ORSR: čakám na prvý výsledok...")
    first_result = wait.until(
        EC.element_to_be_clickable((By.XPATH, first_result_xpath))
    )

    print("[INFO] ORSR: klikám na prvý výsledok...")
    driver.execute_script("arguments[0].click();", first_result)

    wait.until(lambda d: "vypis.asp" in d.current_url)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")


def parse_orsr_basic_info(soup: BeautifulSoup) -> dict:
    result = {
        "obchodne_meno": None,
        "sidlo": None,
        "den_zapisu": None,
        "pravna_forma": None,
        "predmet_podnikania": [],        
        "vyska_zakladneho_imania": None,
        "datum_aktualizacie_dat": None

    }

    field_map = {
        "Obchodné meno": "obchodne_meno",
        "Sídlo": "sidlo",
        "Deň zápisu": "den_zapisu",
        "Právna forma": "pravna_forma",
        "Predmet podnikania": "predmet_podnikania",
        "Výška základného imania": "vyska_zakladneho_imania",
        "Dátum aktualizácie dát": "datum_aktualizacie_dat"
    }

    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue

        label = cells[0].get_text(" ", strip=True).replace(":", "")
        value_cell = cells[1]

        if label not in field_map:
            continue

        key = field_map[label]

        if key == "predmet_podnikania":
            items = [normalize_text(x) for x in value_cell.stripped_strings if normalize_text(x)]
            result["predmet_podnikania"].extend(items)
        else:
            result[key] = normalize_text(value_cell.get_text(" ", strip=True))

    return result


def parse_orsr_statutarny_organ(soup: BeautifulSoup) -> dict:
    result = {
        "typ_organu": None,
        "statutarny_organ": []
    }

    label = None
    for span in soup.select("span.tl"):
        text = span.get_text(" ", strip=True)
        if "Štatutárny orgán" in text:
            label = span
            break

    if not label:
        return result

    row = label.find_parent("tr")
    if not row:
        return result

    cells = row.find_all("td", recursive=False)
    if len(cells) < 2:
        return result

    content_cell = cells[1]
    nested_tables = content_cell.find_all("table", recursive=False)

    for idx, tbl in enumerate(nested_tables, start=1):
        text = tbl.get_text("\n", strip=True)
        lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]

        if not lines:
            continue

        if idx == 1:
            result["typ_organu"] = " ".join(lines)
        else:
            compact_lines = compact_statutory_person(lines)
            result["statutarny_organ"].append(compact_lines)
        

    return result


def parse_orsr_detail(driver) -> dict:
    print("[INFO] ORSR: parsujem detail firmy...")
    html = driver.page_source
    soup = BeautifulSoup(html, "lxml")

    result = {}
    result.update(parse_orsr_basic_info(soup))

    # Štatutárny orgán (špeciálne spracovanie)
    statutar = parse_orsr_statutarny_organ(soup)
    result.update(statutar)

    # Dozorná rada
    dozorna_rada_raw = parse_orsr_section_by_label(soup, "Dozorná rada")
    result["dozorna_rada"] = [
        compact_statutory_person(lines) if len(lines) >= 4 else lines
        for lines in dozorna_rada_raw
    ]

    # Akcie
    result["akcie"] = compact_akcie_section(parse_orsr_section_by_label(soup, "Akcie"))

    # Akcionár
    akcionar_raw = parse_orsr_section_by_label(soup, "Akcionár")
    result["akcionar"] = compact_raw_section(akcionar_raw)

    # Ďalšie právne skutočnosti
    result["dalsie_pravne_skutocnosti"] = parse_orsr_section_by_label(
        soup, "Ďalšie právne skutočnosti"
    )

    return result


# ============================================================
# RPVS
# ============================================================

def rpvs_search_company(driver, wait, ico: str):
    print("[INFO] RPVS: otváram stránku...")
    driver.get(RPVS_URL)

    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    #time.sleep(2)

    rpvs_input = wait.until(
        EC.presence_of_element_located((By.ID, "partner_hladat_text"))
    )

    rpvs_input.clear()
    rpvs_input.send_keys(ico)
    rpvs_input.send_keys(Keys.ENTER)

    wait.until(
        EC.presence_of_element_located((By.ID, "table-VyhladavaniePartnera"))
    )
    #time.sleep(2)


def rpvs_open_first_result(driver, wait):
    first_result_xpath = "//table[@id='table-VyhladavaniePartnera']//tbody/tr[1]/td[4]//a"

    print("[INFO] RPVS: klikám na prvý výsledok...")
    first_result = wait.until(
        EC.element_to_be_clickable((By.XPATH, first_result_xpath))
    )

    driver.execute_script("arguments[0].click();", first_result)

    wait.until(lambda d: "/Detail/" in d.current_url)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")


def parse_rpvs_detail(driver) -> dict:
    print("[INFO] RPVS: parsujem detail...")
    html = driver.page_source
    soup = BeautifulSoup(html, "lxml")

    result = {
        "partner_verejneho_sektora": {},
        "opravnena_osoba": {},
        "konecni_uzivatelia_vyhod": []
    }

    for panel in soup.select("div.panel.panel-default"):
        title_el = panel.select_one("h2.panel-title")
        if not title_el:
            continue

        title = normalize_text(title_el.get_text(strip=True))

        # ========================================================
        # PARTNER VEREJNÉHO SEKTORA
        # ========================================================
        if title == "Partner verejného sektora":
            body = panel.select_one("div.panel-body")
            if not body:
                continue

            for group in body.select("div.form-group"):
                label_el = group.select_one("label")
                value_el = group.select_one("p.form-control-static")

                if not label_el or not value_el:
                    continue

                key = normalize_text(label_el.get_text(" ", strip=True))
                value = normalize_text(value_el.get_text(" ", strip=True))

                result["partner_verejneho_sektora"][key] = value

        # ========================================================
        # OPRÁVNENÁ OSOBA
        # ========================================================
        elif title == "Oprávnená osoba":
            body = panel.select_one("div.panel-body")
            if not body:
                continue

            for group in body.select("div.form-group"):
                label_el = group.select_one("label")
                value_el = group.select_one("p.form-control-static")

                if not label_el or not value_el:
                    continue

                key = normalize_text(label_el.get_text(" ", strip=True))
                value = normalize_text(value_el.get_text(" ", strip=True))

                result["opravnena_osoba"][key] = value

        # ========================================================
        # KONEČNÍ UŽÍVATELIA VÝHOD
        # ========================================================
        elif title == "Koneční užívatelia výhod":
            table = panel.select_one("table")
            if not table:
                continue

            rows = table.select("tbody tr")

            for row in rows:
                cells = row.select("th.hidden-xs, td.hidden-xs")

                if len(cells) < 5:
                    continue

                kuvy = {
                    "Meno a priezvisko": normalize_text(cells[0].get_text(strip=True)),
                    "Dátum narodenia": normalize_text(cells[1].get_text(strip=True)),
                    "Štátna príslušnosť": normalize_text(cells[2].get_text(strip=True)),
                    "Adresa": normalize_text(cells[3].get_text(" ", strip=True)),
                    "Verejný funkcionár": normalize_text(cells[4].get_text(strip=True)),
                }

                result["konecni_uzivatelia_vyhod"].append(kuvy)

    return result

# ============================================================
# FINSTAT
# ============================================================

def finstat_scrape(input_ico: str) -> dict:
    print("[INFO] FinStat: scraping...")
    url = f"https://finstat.sk/vyhladavanie?query={input_ico}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    result = {
        "zakladne_udaje": {},
        "financne_ukazovatele": {}
    }

    response = requests.get(url, headers=headers, timeout=15, verify=False)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Základné info
    element = soup.select_one("div.col-md-8.detail-company-info-side.col-xs-12")
    if element:
        for lead in element.select("div.lead"):
            lead.decompose()

        labels = [
            "IČO",
            "DIČ",
            "IČ DPH",
            "Sídlo",
            "Historický názov",
            "Dátum vzniku",
            "SK NACE",
            "Kategória zamestnancov"
        ]

        pattern = r'(?=\b(?:' + "|".join(re.escape(label) for label in labels) + r')\b)'

        for child in element.find_all(recursive=False):
            text = child.get_text(" ", strip=True)
            if not text:
                continue

            parts = re.split(pattern, text)

            for part in parts:
                part = normalize_text(part)
                if not part:
                    continue

                for label in labels:
                    if part.startswith(label):
                        value = part[len(label):].strip()
                        result["zakladne_udaje"][label] = value
                        break

    # Finančné ukazovatele
    table = soup.select_one("table.table.table-lined.table-condensed.detail-company-financial")
    if table:
        tbody = table.select_one("tbody")

        if tbody:
            for row in tbody.find_all("tr"):
                cells = row.find_all(["th", "td"])

                if len(cells) >= 2:
                    name = normalize_text(cells[0].get_text(" ", strip=True))
                    value = normalize_text(cells[1].get_text(" ", strip=True))

                    if name:
                        result["financne_ukazovatele"][name] = value

    return result


def parse_euro_label(label: str):
    normalized = normalize_text(label).replace("\xa0", " ")
    match = re.search(r"-?\d[\d ]*(?:[,.]\d+)?", normalized)
    if not match:
        return None

    value = float(match.group(0).replace(" ", "").replace(",", "."))
    lowered = normalized.lower()
    if "mld" in lowered:
        value *= 1_000_000_000
    elif "mil" in lowered:
        value *= 1_000_000
    elif "tis" in lowered:
        value *= 1_000
    return value


def euro_label_unit(label: str) -> str:
    lowered = normalize_text(label).lower()
    if "mld" in lowered:
        return "mld.€"
    if "mil" in lowered:
        return "mil.€"
    if "tis" in lowered:
        return "tis.€"
    return "€"


def format_euro_label(value: float, unit: str) -> str:
    divisor = 1
    if unit.startswith("mld"):
        divisor = 1_000_000_000
    elif unit.startswith("mil"):
        divisor = 1_000_000
    elif unit.startswith("tis"):
        divisor = 1_000

    amount = value / divisor
    formatted = f"{amount:.2f}".replace(".", ",")
    return f"~{formatted} {unit}"


def estimate_missing_chart_values(points: list[dict]) -> None:
    known = [point for point in points if isinstance(point.get("value"), (int, float))]
    if len(known) < 2:
        return

    labels = [point.get("value_label", "") for point in known if point.get("value_label")]
    unit = euro_label_unit(labels[0]) if labels else "€"

    y_values = [point["y_svg"] for point in known]
    value_values = [point["value"] for point in known]
    y_mean = sum(y_values) / len(y_values)
    value_mean = sum(value_values) / len(value_values)
    denominator = sum((y_value - y_mean) ** 2 for y_value in y_values)
    if denominator == 0:
        return

    slope = sum((point["y_svg"] - y_mean) * (point["value"] - value_mean) for point in known) / denominator
    intercept = value_mean - slope * y_mean

    for point in points:
        if isinstance(point.get("value"), (int, float)):
            continue
        estimated_value = slope * point["y_svg"] + intercept
        point["value"] = estimated_value
        point["value_label"] = format_euro_label(estimated_value, unit)
        point["value_estimated"] = True


def parse_translate(transform: str | None) -> tuple[float, float]:
    if not transform:
        return 0.0, 0.0
    match = re.search(r"translate\(([-\d.]+)(?:[, ]+([-\d.]+))?\)", transform)
    if not match:
        return 0.0, 0.0
    return float(match.group(1)), float(match.group(2) or 0)


def parse_path_points(path_data: str) -> list[dict]:
    tokens = re.findall(r"[ML]\s*([-\d.]+)\s+([-\d.]+)", path_data or "")
    points = []
    for x_value, y_value in tokens:
        point = {"x_svg": float(x_value), "y_svg": float(y_value)}
        if not any(abs(existing["x_svg"] - point["x_svg"]) < 0.01 for existing in points):
            points.append(point)
    return points


def chart_title_parts(svg) -> tuple[str, str]:
    title = normalize_text(svg.select_one(".highcharts-title").get_text(" ", strip=True)) if svg.select_one(".highcharts-title") else "Graf"
    subtitle = normalize_text(svg.select_one(".highcharts-subtitle").get_text(" ", strip=True)) if svg.select_one(".highcharts-subtitle") else ""
    return title, subtitle


def chart_years(svg) -> list[dict]:
    years = []
    for label in svg.select(".highcharts-xaxis-labels text"):
        text = normalize_text(label.get_text(" ", strip=True))
        if text:
            years.append({"label": text, "x_svg": float(label.get("x", 0))})
    return years


def parse_series_index(class_names) -> int | None:
    if isinstance(class_names, str):
        class_names = class_names.split()
    for class_name in class_names or []:
        match = re.fullmatch(r"highcharts-series-(\d+)", class_name)
        if match:
            return int(match.group(1))
    return None


def finstat_bar_chart_data_from_svg(svg, title: str, subtitle: str, years: list[dict]) -> dict | None:
    legend = []
    legend_by_index = {}
    for item in svg.select(".highcharts-legend-item"):
        series_index = parse_series_index(item.get("class", []))
        if series_index is None:
            continue
        label = normalize_text(item.select_one("text").get_text(" ", strip=True)) if item.select_one("text") else f"Séria {series_index + 1}"
        swatch = item.select_one("rect.highcharts-point") or item.select_one("rect")
        color = swatch.get("fill", "#52606d") if swatch else "#52606d"
        legend_item = {"index": series_index, "label": label, "color": color}
        legend.append(legend_item)
        legend_by_index[series_index] = legend_item

    if not legend or not years:
        return None

    year_rows = [
        {"rok": year["label"], "x_svg": year["x_svg"], "segments": []}
        for year in years
    ]

    for group in svg.select(".highcharts-series.highcharts-column-series"):
        class_names = group.get("class", [])
        if isinstance(class_names, str):
            class_names = class_names.split()
        if "highcharts-markers" in class_names:
            continue
        series_index = parse_series_index(class_names)
        if series_index is None or series_index not in legend_by_index:
            continue
        translate_x, translate_y = parse_translate(group.get("transform"))
        legend_item = legend_by_index[series_index]
        for rect in group.select("rect.highcharts-point"):
            width = float(rect.get("width", 0) or 0)
            height = float(rect.get("height", 0) or 0)
            x_svg = float(rect.get("x", 0) or 0) + translate_x + width / 2
            y_svg = float(rect.get("y", 0) or 0) + translate_y
            nearest = min(year_rows, key=lambda row: abs(row["x_svg"] - x_svg))
            nearest["segments"].append({
                "label": legend_item["label"],
                "color": rect.get("fill") or legend_item["color"],
                "height_svg": height,
                "y_svg": y_svg,
                "series_index": series_index,
            })

    stack_group = svg.select_one(".highcharts-stack-labels")
    stack_translate_x, stack_translate_y = parse_translate(stack_group.get("transform") if stack_group else None)
    for label in svg.select(".highcharts-stack-labels text"):
        text_nodes = [normalize_text(node.get_text(" ", strip=True)) for node in label.select("tspan:not(.highcharts-text-outline)")]
        text_value = next((item for item in text_nodes if item), normalize_text(label.get_text(" ", strip=True)))
        if not text_value:
            continue
        x_svg = float(label.get("x", 0) or 0) + stack_translate_x
        nearest = min(year_rows, key=lambda row: abs(row["x_svg"] - x_svg))
        nearest["total_label"] = text_value
        nearest["total_value"] = parse_euro_label(text_value)
        nearest["total_y_svg"] = float(label.get("y", 0) or 0) + stack_translate_y

    for row in year_rows:
        row["segments"].sort(key=lambda segment: segment["series_index"])
        row["stack_height_svg"] = sum(segment["height_svg"] for segment in row["segments"])

    if not any(row["segments"] for row in year_rows):
        return None

    return {
        "nazov": title,
        "podnazov": subtitle,
        "typ": "bar",
        "legend": sorted(legend, key=lambda item: item["index"]),
        "body": year_rows,
    }


def parse_highcharts_color_index(class_names) -> int | None:
    if isinstance(class_names, str):
        class_names = class_names.split()
    for class_name in class_names or []:
        match = re.fullmatch(r"highcharts-color-(\d+)", class_name)
        if match:
            return int(match.group(1))
    return None


def finstat_pie_chart_data_from_container(soup: BeautifulSoup, svg, title: str, subtitle: str) -> dict | None:
    slices_by_index = {}
    for path in svg.select(".highcharts-pie-series path.highcharts-point"):
        color_index = parse_highcharts_color_index(path.get("class", []))
        if color_index is None:
            continue
        slices_by_index[color_index] = {
            "index": color_index,
            "color": path.get("fill", "#52606d"),
            "path": path.get("d", ""),
        }

    if not slices_by_index:
        return None

    legend = []
    for item in soup.select(".graph-legend .item"):
        name_element = item.select_one(".serieName")
        value_element = item.select_one(".serieValue")
        symbol = item.select_one(".symbol")
        index_text = name_element.get("data-index") if name_element else None
        if index_text is None or not index_text.isdigit():
            continue
        color_index = int(index_text)
        label = normalize_text(name_element.get_text(" ", strip=True)) if name_element else f"Séria {color_index + 1}"
        value_label = normalize_text(value_element.get_text(" ", strip=True)) if value_element else ""
        style = symbol.get("style", "") if symbol else ""
        color_match = re.search(r"background-color\s*:\s*([^;]+)", style)
        color = color_match.group(1).strip() if color_match else slices_by_index.get(color_index, {}).get("color", "#52606d")
        slice_data = slices_by_index.get(color_index, {"index": color_index, "path": ""})
        slice_data.update({
            "label": label,
            "value_label": value_label,
            "value": parse_euro_label(value_label),
            "color": color,
        })
        legend.append(slice_data)

    body = sorted(legend or slices_by_index.values(), key=lambda item: item.get("index", 0))
    if not body:
        return None

    return {
        "nazov": title,
        "podnazov": subtitle,
        "typ": "pie",
        "body": body,
    }


def finstat_chart_data_from_svg(svg_html: str) -> dict | None:
    soup = BeautifulSoup(svg_html, "lxml")
    svg = soup.select_one("svg.highcharts-root") or soup.select_one("svg")
    if not svg:
        return None

    title, subtitle = chart_title_parts(svg)
    years = chart_years(svg)

    if svg.select_one(".highcharts-pie-series"):
        pie_chart = finstat_pie_chart_data_from_container(soup, svg, title, subtitle)
        if pie_chart:
            return pie_chart

    if svg.select_one(".highcharts-column-series"):
        bar_chart = finstat_bar_chart_data_from_svg(svg, title, subtitle, years)
        if bar_chart:
            return bar_chart

    graph_path = None
    for path in svg.select("path.highcharts-graph"):
        class_names = path.get("class", [])
        if isinstance(class_names, str):
            class_names = class_names.split()
        if "highcharts-zone-graph-0" in class_names or "highcharts-zone-graph-1" in class_names:
            continue
        graph_path = path
        break
    graph_path = graph_path or svg.select_one("path.highcharts-graph")
    if not graph_path:
        return None

    translate_x, translate_y = parse_translate(graph_path.find_parent("g").get("transform") if graph_path.find_parent("g") else None)
    points = parse_path_points(graph_path.get("d", ""))
    if len(points) < 2:
        return None

    for index, point in enumerate(points):
        point["x_svg"] += translate_x
        point["y_svg"] += translate_y
        if index < len(years):
            point["rok"] = years[index]["label"]

    label_candidates = []
    labels_group = svg.select_one(".highcharts-data-labels")
    labels_translate_x, labels_translate_y = parse_translate(labels_group.get("transform") if labels_group else None)
    for label in svg.select(".highcharts-data-label"):
        text_nodes = [normalize_text(node.get_text(" ", strip=True)) for node in label.select("tspan:not(.highcharts-text-outline)")]
        text_value = next((item for item in text_nodes if item), "")
        if not text_value:
            continue
        label_x, label_y = parse_translate(label.get("transform"))
        # Highcharts positions the label by its left edge. This offset maps the visible label near its point.
        estimated_point_x = labels_translate_x + label_x + 36
        label_candidates.append({
            "x_svg": estimated_point_x,
            "y_svg": labels_translate_y + label_y,
            "label": text_value,
            "value": parse_euro_label(text_value),
        })

    unused_points = set(range(len(points)))
    for candidate in label_candidates:
        if not unused_points:
            break
        nearest_index = min(unused_points, key=lambda idx: abs(points[idx]["x_svg"] - candidate["x_svg"]))
        points[nearest_index]["value_label"] = candidate["label"]
        points[nearest_index]["value"] = candidate["value"]
        unused_points.remove(nearest_index)

    estimate_missing_chart_values(points)

    return {
        "nazov": title,
        "podnazov": subtitle,
        "typ": "line",
        "body": points,
    }


def finstat_graph_screenshots(driver, wait, input_ico: str) -> list[dict]:
    print("[INFO] FinStat: snímam grafy...")
    url = f"https://finstat.sk/vyhladavanie?query={input_ico}"

    driver.get(url)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    #time.sleep(3)

    graph_elements = driver.find_elements(By.CSS_SELECTOR, ".graph")
    graph_names = ["Zisk", "Tržby", "Celkové Výnosy", "Aktíva", "Pasíva"]
    graphs = []

    for idx, element in enumerate(graph_elements, start=1):
        if len(graphs) >= len(graph_names):
            break
        try:
            if not element.is_displayed():
                continue

            size = element.size or {}
            if size.get("width", 0) < 50 or size.get("height", 0) < 50:
                continue

            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
            time.sleep(0.5)

            title = driver.execute_script(
                """
                const el = arguments[0];
                const container = el.closest('section, article, .panel, .card, div') || el.parentElement;
                const heading = container ? container.querySelector('h1, h2, h3, h4, .title') : null;
                return (heading && heading.innerText && heading.innerText.trim()) ||
                       el.getAttribute('aria-label') ||
                       el.getAttribute('id') ||
                       `Graf ${arguments[1]}`;
                """,
                element,
                idx,
            )

            graph_name = graph_names[len(graphs)]
            chart_html = driver.execute_script(
                """
                const el = arguments[0];
                const container = el.closest('.chart, .panel, .col-sm-6') || el;
                return container.outerHTML;
                """,
                element,
            ) or element.get_attribute("outerHTML") or ""
            chart_data = finstat_chart_data_from_svg(chart_html)
            if chart_data:
                chart_data["nazov"] = graph_name
                image = None
            else:
                image = f"data:image/png;base64,{element.screenshot_as_base64}"
            graphs.append({
                "nazov": graph_name,
                "image": image,
                "chart_data": chart_data,
            })
        except Exception as e:
            print(f"[WARN] FinStat: graf {idx} sa nepodarilo zosnímať: {type(e).__name__}: {e}")
            if os.getenv("DEBUG_PORTAL_ERRORS") == "1":
                traceback.print_exc()

    print(f"[INFO] FinStat: počet zosnímaných grafov: {len(graphs)}")
    return graphs

# ============================================================
# CRZ
# ============================================================

def absolute_crz_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"https://www.crz.gov.sk{href}"
    return f"https://www.crz.gov.sk/{href}"


def crz_scrape(input_ico: str, limit: int = 10) -> dict:
    print("[INFO] CRZ: scraping...")
    response = requests.get(
        CRZ_URL,
        params={"search": input_ico},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
        timeout=20,
        verify=False,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    records = []

    for row in soup.select("table.table_list tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 5:
            continue

        date_parts = [normalize_text(part) for part in cells[0].stripped_strings if normalize_text(part)]
        date = " ".join(date_parts)

        contract_link = cells[1].find("a", href=True)
        contract_number = cells[1].find("span")

        record = {
            "datum": date,
            "nazov_zmluvy": normalize_text(contract_link.get_text(" ", strip=True)) if contract_link else normalize_text(cells[1].get_text(" ", strip=True)),
            "cislo_zmluvy": normalize_text(contract_number.get_text(" ", strip=True)) if contract_number else "",
            "link": absolute_crz_url(contract_link.get("href", "")) if contract_link else "",
            "cena": normalize_text(cells[2].get_text(" ", strip=True)),
            "dodavatel": normalize_text(cells[3].get_text(" ", strip=True)),
            "odberatel": normalize_text(cells[4].get_text(" ", strip=True)),
        }
        records.append(record)

        if len(records) >= limit:
            break

    return {"zmluvy": records}
# ============================================================
# RUZ
# ============================================================
def ruz_search_company(driver, wait, ico: str):
    print("[INFO] RUZ: otváram stránku...")
    driver.get(RUZ_URL)

    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(2)

    print("[INFO] RUZ: hľadám input...")

    search_input = wait.until(
        EC.presence_of_element_located((By.ID, "input_search"))
    )

    search_input.clear()
    search_input.send_keys(ico)

    # počkaj na dropdown suggestions
    print("[INFO] RUZ: čakám na autocomplete výsledky...")

    first_result = wait.until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//ul[contains(@class,'ui-autocomplete')]//li[1]//a"
        ))
    )

    print("[INFO] RUZ: klikám prvý výsledok...")
    driver.execute_script("arguments[0].click();", first_result)

    # počkaj na detail
    wait.until(lambda d: "/show/" in d.current_url)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#allWrappers, #allWrapers"))
        )
    except Exception:
        print("[INFO] RUZ: allWrappers/allWrapers sa nenačítal počas krátkeho čakania.")

    print("[SUCCESS] RUZ detail otvorený.")


def ruz_open_annual_reports(driver) -> bool:
    print("[INFO] RUZ: prepínam na Výročné správy...")
    try:
        link = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "#link-ANNUAL_REPORT, a[data-statementtype='ANNUAL_REPORT']"
            ))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", link)
        driver.execute_script("arguments[0].click();", link)
        time.sleep(2)
        return True
    except Exception as e:
        print(f"[INFO] RUZ: Výročné správy sa nepodarilo prepnúť, pokračujem bez pádu: {type(e).__name__}: {e}")
        if os.getenv("DEBUG_PORTAL_ERRORS") == "1":
            traceback.print_exc()
        return False


# ============================================================
# RUZ PARSE
# ============================================================

def absolute_ruz_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"https://registeruz.sk{href}"
    return f"https://registeruz.sk/{href}"


def parse_ruz_all_wrappers(soup: BeautifulSoup, limit: int = 5, wrapper_selector: str | None = None) -> list[dict]:
    selector = wrapper_selector or "#allWrappers, #allWrapers"
    wrapper = soup.select_one(selector)
    if not wrapper:
        print("[INFO] RUZ: allWrappers/allWrapers sa nenašiel.")
        return []

    for element in wrapper.select("script, style, button, .icon-duplicate, i.icon"):
        element.decompose()

    aria_table = wrapper.select_one('[role="table"], .b-items-table-list')
    if aria_table:
        headers = [
            normalize_text(header.get_text(" ", strip=True))
            for header in aria_table.select('[role="columnheader"]')
        ]
        headers = [header for header in headers if header]
        records = []

        items = aria_table.select(".listing > .item") or aria_table.select(".item")
        for item in items:
            title_row = item.select_one("a.title .row") or item.select_one(".row")
            cells = []
            if title_row:
                cells = [
                    normalize_text(cell.get_text(" ", strip=True))
                    for cell in title_row.select('[role="cell"]')
                ]
                cells = [cell for cell in cells]

            record = {}
            for idx, value in enumerate(cells):
                label = headers[idx] if idx < len(headers) else f"stlpec_{idx + 1}"
                record[label] = value

            documents = []
            collapse = item.select_one(".collapse")
            if collapse:
                for link in collapse.select('a[href*="/financialreport/show/"], a[href*="/financialreport/attachment/"]'):
                    title = normalize_text(link.select_one(".text-primary").get_text(" ", strip=True)) if link.select_one(".text-primary") else ""
                    kind = normalize_text(link.select_one(".text-black").get_text(" ", strip=True)) if link.select_one(".text-black") else ""
                    source = normalize_text(link.select_one(".text-gray").get_text(" ", strip=True)) if link.select_one(".text-gray") else ""
                    href = absolute_ruz_url(link.get("href") or "")

                    documents.append({
                        "nazov": title.rstrip(":"),
                        "typ": kind,
                        "zdroj": source,
                        "url": href,
                    })

            if documents:
                record["dokumenty"] = documents

            if record:
                records.append(record)

            if len(records) >= limit:
                return records

        if records:
            return records

    table = wrapper.find("table")
    if table:
        headers = [normalize_text(cell.get_text(" ", strip=True)) for cell in table.select("thead th")]
        records = []

        for row in table.select("tbody tr"):
            cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"], recursive=False)]
            cells = [cell for cell in cells if cell]
            if not cells:
                continue

            if headers and len(headers) == len(cells):
                records.append({header or f"stlpec_{idx}": value for idx, (header, value) in enumerate(zip(headers, cells), start=1)})
            else:
                records.append({f"stlpec_{idx}": value for idx, value in enumerate(cells, start=1)})

            if len(records) >= limit:
                return records

    return []


def parse_ruz_detail(driver, annual_reports: list[dict] | None = None) -> dict:
    print("[INFO] RUZ: parsujem detail...")

    html = driver.page_source
    soup = BeautifulSoup(html, "lxml")
    statements = parse_ruz_all_wrappers(
        soup,
        limit=5,
        wrapper_selector="#wrapper-INDIVIDUAL, #allWrappers, #allWrapers",
    )

    result = {
        "uctovne_zavierky": statements,
        "vyrocne_spravy": annual_reports or [],
        "zaznamy": statements,
    }

    container = soup.select_one('div[data-tab-container="1"]')
    if not container:
        print("[WARN] RUZ: nenašiel sa hlavný container")
        return result
        
    # odstráni UI prvky (napr. copy icony)
    for icon in container.select(".icon-duplicate, .btn-link, i.icon"):
        icon.extract()
    
    # názov
    title = container.select_one("h3, h1")
    if title:
        result["nazov"] = normalize_text(title.get_text())

    # info bloky
    for block in container.select("div.b-content div.fs-14.text-gray"):

        # iba text uzlov (bez vnorených UI vecí)
        texts = list(block.stripped_strings)

        if len(texts) < 2:
            continue

        label = normalize_text(texts[0].replace(":", ""))

        # špeciálne prípady
        if label == "SK NACE":
            value = clean_value(" ".join(block.stripped_strings))

        elif label == "Adresa":
            value = clean_value(", ".join([normalize_text(x) for x in block.stripped_strings]))


        else:
            value = clean_value(normalize_text(" ".join(texts[1:])))

        result[label] = value

    return result

# ============================================================
# ORCHESTRATION
# ============================================================

NO_INFO_MESSAGE = "Na tomto portáli nie sú informácie o firme."
AVAILABLE_SOURCES = {"orsr", "rpvs", "finstat", "ruz", "crz"}


def no_info_result() -> dict:
    return {"message": NO_INFO_MESSAGE}


def has_portal_data(value) -> bool:
    if value is None:
        return False

    if isinstance(value, dict):
        return any(has_portal_data(item) for item in value.values())

    if isinstance(value, list):
        return any(has_portal_data(item) for item in value)

    if isinstance(value, str):
        return bool(value.strip())

    return True


def run_portal_scrape(portal_name: str, scrape_func) -> dict:
    try:
        result = scrape_func()
        if not has_portal_data(result):
            print(f"[INFO] {portal_name}: bez výsledkov.")
            return no_info_result()
        return result
    except Exception as e:
        print(f"[WARN] {portal_name}: nepodarilo sa získať údaje: {type(e).__name__}: {e}")
        if os.getenv("DEBUG_PORTAL_ERRORS") == "1":
            traceback.print_exc()
        return no_info_result()


def browser_scrape(scrape_func):
    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 20)
        return scrape_func(driver, wait)
    finally:
        if driver:
            driver.quit()


def scrape_subject_parallel(ico: str, selected_sources: set[str]) -> dict:
    subjekt = {"ico": ico}
    for source in selected_sources:
        subjekt[source] = no_info_result()

    def scrape_orsr_browser(driver, wait):
        orsr_search_company(driver, wait, ico)
        orsr_open_first_result(driver, wait)
        return parse_orsr_detail(driver)

    def scrape_rpvs_browser(driver, wait):
        rpvs_search_company(driver, wait, ico)
        rpvs_open_first_result(driver, wait)
        return parse_rpvs_detail(driver)

    def scrape_ruz_browser(driver, wait):
        ruz_search_company(driver, wait, ico)
        detail = parse_ruz_detail(driver)

        initial_soup = BeautifulSoup(driver.page_source, "lxml")
        annual_reports = parse_ruz_all_wrappers(
            initial_soup,
            limit=5,
            wrapper_selector="#wrapper-ANNUAL_REPORT",
        )

        if not annual_reports and ruz_open_annual_reports(driver):
            annual_soup = BeautifulSoup(driver.page_source, "lxml")
            annual_reports = parse_ruz_all_wrappers(
                annual_soup,
                limit=5,
                wrapper_selector="#wrapper-ANNUAL_REPORT",
            )

        detail["vyrocne_spravy"] = annual_reports
        return detail

    def scrape_finstat_parallel():
        result = finstat_scrape(ico)
        try:
            result["grafy"] = browser_scrape(lambda driver, wait: finstat_graph_screenshots(driver, wait, ico))
        except Exception as e:
            print(f"[WARN] FinStat: grafy sa nepodarilo získať: {type(e).__name__}: {e}")
            if os.getenv("DEBUG_PORTAL_ERRORS") == "1":
                traceback.print_exc()
            result["grafy"] = []
        return result

    tasks = {}
    if "orsr" in selected_sources:
        tasks["orsr"] = ("ORSR", lambda: browser_scrape(scrape_orsr_browser))
    if "rpvs" in selected_sources:
        tasks["rpvs"] = ("RPVS", lambda: browser_scrape(scrape_rpvs_browser))
    if "finstat" in selected_sources:
        tasks["finstat"] = ("FinStat", scrape_finstat_parallel)
    if "ruz" in selected_sources:
        tasks["ruz"] = ("RUZ", lambda: browser_scrape(scrape_ruz_browser))
    if "crz" in selected_sources:
        tasks["crz"] = ("CRZ", lambda: crz_scrape(ico))

    max_workers = int(os.getenv("PARALLEL_PORTAL_WORKERS", str(min(len(tasks), 5) or 1)))
    print(f"[INFO] Paralelné scrapovanie portálov zapnuté, workers={max_workers}.")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {
            executor.submit(run_portal_scrape, portal_name, scrape_func): source
            for source, (portal_name, scrape_func) in tasks.items()
        }
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            subjekt[source] = future.result()

    return subjekt


def scrape_subject(ico: str, sources: set[str] | None = None) -> dict:
    selected_sources = sources or AVAILABLE_SOURCES
    if os.getenv("PARALLEL_PORTAL_SCRAPES") == "1":
        return scrape_subject_parallel(ico, selected_sources)

    subjekt = {"ico": ico}

    for source in selected_sources:
        subjekt[source] = no_info_result()

    driver = None

    try:
        def ensure_browser():
            nonlocal driver
            if driver is None:
                driver = create_driver()
            return driver, WebDriverWait(driver, 20)

        def scrape_orsr():
            driver, wait = ensure_browser()
            orsr_search_company(driver, wait, ico)
            orsr_open_first_result(driver, wait)
            return parse_orsr_detail(driver)

        def scrape_rpvs():
            driver, wait = ensure_browser()
            rpvs_search_company(driver, wait, ico)
            rpvs_open_first_result(driver, wait)
            return parse_rpvs_detail(driver)

        def scrape_ruz():
            driver, wait = ensure_browser()
            ruz_search_company(driver, wait, ico)
            detail = parse_ruz_detail(driver)

            initial_soup = BeautifulSoup(driver.page_source, "lxml")
            annual_reports = parse_ruz_all_wrappers(
                initial_soup,
                limit=5,
                wrapper_selector="#wrapper-ANNUAL_REPORT",
            )

            if not annual_reports and ruz_open_annual_reports(driver):
                annual_soup = BeautifulSoup(driver.page_source, "lxml")
                annual_reports = parse_ruz_all_wrappers(
                    annual_soup,
                    limit=5,
                    wrapper_selector="#wrapper-ANNUAL_REPORT",
                )

            detail["vyrocne_spravy"] = annual_reports
            return detail

        def scrape_finstat():
            result = finstat_scrape(ico)
            try:
                driver, wait = ensure_browser()
                result["grafy"] = finstat_graph_screenshots(driver, wait, ico)
            except Exception as e:
                print(f"[WARN] FinStat: grafy sa nepodarilo získať: {type(e).__name__}: {e}")
                if os.getenv("DEBUG_PORTAL_ERRORS") == "1":
                    traceback.print_exc()
                result["grafy"] = []
            return result

        if "orsr" in selected_sources:
            subjekt["orsr"] = run_portal_scrape("ORSR", scrape_orsr)
        if "rpvs" in selected_sources:
            subjekt["rpvs"] = run_portal_scrape("RPVS", scrape_rpvs)
        if "finstat" in selected_sources:
            subjekt["finstat"] = run_portal_scrape("FinStat", scrape_finstat)
        if "ruz" in selected_sources:
            subjekt["ruz"] = run_portal_scrape("RUZ", scrape_ruz)
        if "crz" in selected_sources:
            subjekt["crz"] = run_portal_scrape("CRZ", lambda: crz_scrape(ico))

        return subjekt

    except Exception:
        print("[ERROR] scrape_subject zlyhal pred spustením portálov.")
        traceback.print_exc()
        if driver:
            save_debug(driver, prefix=f"{ico}_debug")
        raise

    finally:
        if driver:
            driver.quit()


def main():
    ico = os.getenv("ICO", "36785512")

    try:
        subjekt = scrape_subject(ico)

        print("\n=== VÝSLEDNÝ SUBJEKT ===\n")
        print(json.dumps(subjekt, ensure_ascii=False, indent=2))

        with open(f"{ico}_result.json", "w", encoding="utf-8") as f:
            json.dump(subjekt, f, ensure_ascii=False, indent=2)

        print(f"[INFO] Výsledok uložený do {ico}_result.json")

    except Exception as e:
        print("[FATAL] Program zlyhal.")
        print(type(e).__name__, str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()

