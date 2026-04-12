"""
Visa Bulletin Scraper - F4 Category, China (mainland born)
Fetches only missing months, caches results in data.json.
"""

import re
import sys
import json
import os
from datetime import date, datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "-q"])
    import requests
    from bs4 import BeautifulSoup

BASE_URL   = "https://travel.state.gov"
INDEX_URL  = f"{BASE_URL}/content/travel/en/legal/visa-law0/visa-bulletin.html"
CACHE_FILE = "data.json"

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VisaBulletinScraper/1.0)"}


def parse_priority_date(raw):
    raw = raw.strip()
    m = re.match(r"^(\d{1,2})([A-Z]{3})(\d{2,4})$", raw.upper())
    if m:
        day, mon, yr = int(m.group(1)), m.group(2), m.group(3)
        month_num = MONTH_ABBR.get(mon)
        if month_num:
            year = int(yr)
            if year < 100:
                year += 2000 if year <= 30 else 1900
            try:
                return date(year, month_num, day).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return raw


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loaded {len(data)} cached entries from {CACHE_FILE}")
        return {(r["year"], r["month"]): r for r in data}
    return {}


def save_cache(cache_dict, n_months=12):
    records = sorted(cache_dict.values(),
                     key=lambda r: date(r["year"], r["month"], 1),
                     reverse=True)
    records = records[:n_months]  # keep only latest 12
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"Saved {len(records)} entries to {CACHE_FILE} (latest {n_months} months only)")


def get_bulletin_links(n_months=12):
    resp = requests.get(INDEX_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/visa-bulletin/\d{4}/visa-bulletin-for-", href):
            m = re.search(r"visa-bulletin-for-([a-z]+)-(\d{4})\.html", href)
            if m:
                month_name, year = m.group(1), int(m.group(2))
                month_num = MONTH_NAMES.get(month_name.lower())
                if month_num:
                    full_url = BASE_URL + href if href.startswith("/") else href
                    links.append({
                        "label":    f"{month_name.capitalize()} {year}",
                        "url":      full_url,
                        "year":     year,
                        "month":    month_num,
                        "sort_key": date(year, month_num, 1),
                    })

    seen, unique = set(), []
    for item in links:
        key = (item["year"], item["month"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    unique.sort(key=lambda x: x["sort_key"], reverse=True)
    return unique[:n_months]


def get_release_date(soup):
    text = soup.get_text(" ", strip=True)
    m = re.search(r"CA/VO[:\s]+([A-Za-z]+ \d{1,2},?\s*\d{4})", text)
    if m:
        try:
            raw = m.group(1).replace(",", "").strip()
            return datetime.strptime(raw, "%B %d %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    matches = re.findall(r"([A-Za-z]+ \d{1,2}, \d{4})", text)
    for candidate in reversed(matches):
        try:
            return datetime.strptime(candidate, "%B %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
    return "N/A"


def find_china_f4(soup, table_type):
    elements = soup.find_all(["h1", "h2", "h3", "h4", "p", "b", "strong", "table"])
    current_section = None
    final_action_tables, filing_tables = [], []

    for el in elements:
        text = el.get_text(" ", strip=True).upper()
        if el.name == "table":
            if current_section == "FINAL_ACTION":
                final_action_tables.append(el)
            elif current_section == "DATES_FOR_FILING":
                filing_tables.append(el)
        else:
            if "FINAL ACTION" in text and "FAMIL" in text:
                current_section = "FINAL_ACTION"
            elif ("DATES FOR FILING" in text or "DATE FOR FILING" in text) and "FAMIL" in text:
                current_section = "DATES_FOR_FILING"
            elif "EMPLOYMENT" in text and ("FINAL ACTION" in text or "DATES FOR FILING" in text):
                current_section = None

    target = final_action_tables if table_type == "final_action" else filing_tables

    for table in target:
        rows = table.find_all("tr")
        china_col = None
        for row in rows:
            headers = row.find_all(["th", "td"])
            for i, h in enumerate(headers):
                if "CHINA" in h.get_text(" ", strip=True).upper():
                    china_col = i
                    break
            if china_col is not None:
                break
        if china_col is None:
            continue
        for row in rows:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            if re.match(r"F\s*4", cells[0].get_text(" ", strip=True).upper()):
                if china_col < len(cells):
                    return cells[china_col].get_text(" ", strip=True)

    return "N/A"


def scrape_bulletin(bulletin):
    try:
        resp = requests.get(bulletin["url"], headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return {
            "bulletin":          bulletin["label"],
            "month":             bulletin["month"],
            "year":              bulletin["year"],
            "release_date":      get_release_date(soup),
            "final_action_date": parse_priority_date(find_china_f4(soup, "final_action")),
            "dates_for_filing":  parse_priority_date(find_china_f4(soup, "dates_for_filing")),
            "url":               bulletin["url"],
        }
    except Exception as e:
        return {
            "bulletin":          bulletin["label"],
            "month":             bulletin["month"],
            "year":              bulletin["year"],
            "release_date":      "ERROR",
            "final_action_date": f"ERROR: {e}",
            "dates_for_filing":  f"ERROR: {e}",
            "url":               bulletin["url"],
        }


def to_markdown_table(results):
    lines = [
        "| Bulletin | Release Date | Final Action Date (China F4) | Date for Filing (China F4) |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['bulletin']} | {r['release_date']} | {r['final_action_date']} | {r['dates_for_filing']} |"
        )
    return "\n".join(lines)


def main(n_months=12):
    cache = load_cache()
    bulletins = get_bulletin_links(n_months)

    fetched = 0
    for b in bulletins:
        key = (b["year"], b["month"])
        if key in cache:
            print(f"  [cached] {b['label']}")
        else:
            print(f"  [fetch]  {b['label']} ...")
            result = scrape_bulletin(b)
            cache[key] = result
            fetched += 1

    save_cache(cache)
    print(f"Done — {fetched} new, {len(bulletins) - fetched} from cache")

    # Return sorted newest-first, limited to n_months
    results = sorted(cache.values(),
                     key=lambda r: date(r["year"], r["month"], 1),
                     reverse=True)
    return results[:n_months]


if __name__ == "__main__":
    results = main(12)
    print("\n" + to_markdown_table(results))
