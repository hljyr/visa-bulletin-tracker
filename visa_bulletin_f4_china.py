"""
Visa Bulletin Scraper - F4 Category, China (mainland born)
Fetches the last 12 months of bulletins and extracts:
  - Final Action Date (Table A)
  - Date for Filing (Table B)
for the F4 family preference category, China column.
"""

import re
import sys
from datetime import date, datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "-q"])
    import requests
    from bs4 import BeautifulSoup

BASE_URL = "https://travel.state.gov"
INDEX_URL = f"{BASE_URL}/content/travel/en/legal/visa-law0/visa-bulletin.html"

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
    """Convert ddMMMYY or ddMMMYYYY (e.g. 08JUN08 or 08JUN2008) to YYYY-MM-DD.
    Returns raw string unchanged if it cannot be parsed (e.g. 'C', 'U', 'N/A')."""
    raw = raw.strip()
    # Match formats like 08JUN08 or 08JUN2008
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
                    # Format label as "April 2026"
                    label = f"{month_name.capitalize()} {year}"
                    links.append({
                        "label": label,
                        "url": full_url,
                        "year": year,
                        "month": month_num,
                        "sort_key": date(year, month_num, 1),
                    })

    seen = set()
    unique = []
    for item in links:
        key = (item["year"], item["month"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    unique.sort(key=lambda x: x["sort_key"], reverse=True)
    return unique[:n_months]


def get_release_date(soup):
    """Extract the publication date from the bulletin page.
    Looks for patterns like 'CA/VO: March 4, 2026' or similar date lines."""
    text = soup.get_text(" ", strip=True)

    # Pattern: CA/VO: Month Day, Year
    m = re.search(r"CA/VO[:\s]+([A-Za-z]+ \d{1,2},?\s*\d{4})", text)
    if m:
        try:
            raw = m.group(1).replace(",", "").strip()
            dt = datetime.strptime(raw, "%B %d %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Fallback: look for any "Month DD, YYYY" near the bottom
    matches = re.findall(r"([A-Za-z]+ \d{1,2}, \d{4})", text)
    if matches:
        for candidate in reversed(matches):
            try:
                dt = datetime.strptime(candidate, "%B %d, %Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

    return "N/A"


def find_china_f4(soup, table_type):
    elements = soup.find_all(["h1", "h2", "h3", "h4", "p", "b", "strong", "table"])
    current_section = None
    final_action_tables = []
    filing_tables = []

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

    target_tables = final_action_tables if table_type == "final_action" else filing_tables

    for table in target_tables:
        rows = table.find_all("tr")
        china_col = None
        for row in rows:
            headers = row.find_all(["th", "td"])
            header_texts = [h.get_text(" ", strip=True).upper() for h in headers]
            for i, ht in enumerate(header_texts):
                if "CHINA" in ht:
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
            first_cell = cells[0].get_text(" ", strip=True).upper()
            if re.match(r"F\s*4", first_cell):
                if china_col < len(cells):
                    return cells[china_col].get_text(" ", strip=True)

    return "N/A"


def scrape_bulletin(bulletin):
    try:
        resp = requests.get(bulletin["url"], headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        raw_final  = find_china_f4(soup, "final_action")
        raw_filing = find_china_f4(soup, "dates_for_filing")

        return {
            "bulletin":          bulletin["label"],
            "month":             bulletin["month"],
            "year":              bulletin["year"],
            "release_date":      get_release_date(soup),
            "final_action_date": parse_priority_date(raw_final),
            "dates_for_filing":  parse_priority_date(raw_filing),
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
    print(f"Fetching last {n_months} Visa Bulletins for F4 / China (mainland born)...")
    bulletins = get_bulletin_links(n_months)
    if not bulletins:
        print("ERROR: Could not find any bulletin links.")
        sys.exit(1)

    print(f"Found {len(bulletins)} bulletins. Scraping...")
    results = []
    for i, b in enumerate(bulletins, 1):
        print(f"  [{i}/{len(bulletins)}] {b['label']} ...")
        result = scrape_bulletin(b)
        results.append(result)

    return results


if __name__ == "__main__":
    results = main(12)
    print("\n" + to_markdown_table(results))
