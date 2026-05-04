"""
╔══════════════════════════════════════════════════════════════════╗
║           EMPLOITUNISIE.COM JOB SCRAPER                          ║
║  Scrapes job listings from https://www.emploitunisie.com/        ║
║  Output: data/raw_emploitunisie_jobs.csv                         ║
╚══════════════════════════════════════════════════════════════════╝

Selectors confirmed via debug inspection on 2026-04-27:
    Card container : div.last-offers-item
    Job title      : h3 (no class, first inside card)
    Details block  : div.last-offers-details
    Company        : text node after date inside details
    Date           : first text segment in details (DD.MM.YYYY)
    Location       : text containing "Région de :"
    Link           : first <a href> inside card

Fields extracted per job:
    source, title, company, location, date, link

Dependencies:
    pip install selenium webdriver-manager beautifulsoup4 pandas lxml
"""

# ─────────────────────────────────────────────────────────────────
# SECTION 1 — IMPORTS
# ─────────────────────────────────────────────────────────────────
import os
import re
import time
import logging

import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# ─────────────────────────────────────────────────────────────────
# SECTION 2 — CONFIGURATION
# ─────────────────────────────────────────────────────────────────

# Homepage shows latest jobs; paginated search for deeper scraping
# Page 1 = most recent listings
BASE_URL = "https://www.emploitunisie.com/recherche-jobs-tunisie?page={}"

# Also scrape the homepage (page 0 = homepage latest offers)
HOME_URL = "https://www.emploitunisie.com/"

# Output CSV path
OUTPUT_PATH = "data/raw_emploitunisie_jobs.csv"

# Number of paginated pages to scrape (each ~15 jobs)
MAX_PAGES = 30

# Polite delay between page requests (seconds)
PAGE_DELAY = 2

# Max seconds to wait for JS-rendered content
CONTENT_TIMEOUT = 10

# Realistic browser User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ── Confirmed CSS selectors (from debug inspection) ───────────────
CARD_SELECTOR       = "div.last-offers-item"       # Each job card
DETAILS_SELECTOR    = "div.last-offers-details"    # Company/date/location block
SEARCH_CARD         = "div.search-results-format"  # Card on search/paginated pages


# ─────────────────────────────────────────────────────────────────
# SECTION 3 — LOGGING SETUP
# ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# SECTION 4 — DRIVER SETUP
# ─────────────────────────────────────────────────────────────────

def setup_driver(headless: bool = False) -> webdriver.Chrome:
    """
    Initialize Chrome WebDriver with anti-detection measures.

    Args:
        headless: Run without visible browser window.
                  Set False first to verify, True for automated runs.

    Returns:
        Configured Chrome WebDriver instance.
    """
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # ── Anti-bot-detection ─────────────────────────────────────────
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"user-agent={USER_AGENT}")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    # Hide navigator.webdriver JS property (checked by many sites)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": (
                "Object.defineProperty(navigator, 'webdriver', "
                "{get: () => undefined})"
            )
        },
    )

    log.info("Chrome WebDriver initialized (headless=%s)", headless)
    return driver


# ─────────────────────────────────────────────────────────────────
# SECTION 5 — COOKIE CONSENT HANDLER
# ─────────────────────────────────────────────────────────────────

def accept_cookies(driver: webdriver.Chrome, timeout: int = 5) -> None:
    """
    Click cookie/GDPR consent button if present.

    Searches for buttons with common French/English consent words.

    Args:
        driver:  Active WebDriver session.
        timeout: Seconds to wait before giving up.
    """
    consent_xpath = (
        "//button["
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accepter') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continuer') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok')"
        "]"
    )
    try:
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, consent_xpath))
        )
        btn.click()
        log.info("  ✓ Cookie consent accepted")
        time.sleep(1)
    except Exception:
        log.info("  ℹ No cookie banner detected")


# ─────────────────────────────────────────────────────────────────
# SECTION 6 — DYNAMIC CONTENT WAIT
# ─────────────────────────────────────────────────────────────────

def wait_for_content(driver: webdriver.Chrome, timeout: int = CONTENT_TIMEOUT) -> bool:
    """
    Wait until job cards appear in the DOM.

    Targets the confirmed card selectors from debug inspection:
        - div.last-offers-item  (homepage)
        - div.search-results-format  (search/paginated pages)

    Args:
        driver:  Active WebDriver session.
        timeout: Maximum seconds to wait.

    Returns:
        True if content appeared, False on timeout.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.last-offers-item, div.search-results-format")
            )
        )
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────
# SECTION 7 — JOB CARD DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_job_cards(soup: BeautifulSoup) -> list:
    """
    Locate job cards using confirmed selectors, with fallbacks.

    Priority order (from debug inspection):
        1. div.last-offers-item     — homepage latest jobs section
        2. div.search-results-format — search/paginated results
        3. div.card                 — generic card fallback
        4. Heuristic: div with h3 + link

    Args:
        soup: BeautifulSoup of the fully-rendered page.

    Returns:
        List of Tag objects for individual job cards.
    """
    # Strategy 1: Homepage cards (confirmed: 21 found)
    cards = soup.find_all("div", class_="last-offers-item")
    if cards:
        log.info("  ✓ Found %d card(s) via 'last-offers-item'", len(cards))
        return cards

    # Strategy 2: Search/paginated page cards (confirmed: 16 found)
    cards = soup.find_all("div", class_="search-results-format")
    if cards:
        log.info("  ✓ Found %d card(s) via 'search-results-format'", len(cards))
        return cards

    # Strategy 3: Generic card divs
    cards = soup.find_all("div", class_="card")
    if cards:
        log.info("  ✓ Found %d card(s) via 'card'", len(cards))
        return cards

    # Strategy 4: Heuristic — any div with an h3 and a link
    fallback = [
        div for div in soup.find_all("div")
        if div.find("h3") and div.find("a", href=True)
    ]
    log.warning("  ⚠ Using heuristic fallback: %d candidate(s)", len(fallback))
    return fallback


# ─────────────────────────────────────────────────────────────────
# SECTION 8 — SINGLE CARD PARSER
# ─────────────────────────────────────────────────────────────────

def parse_card(card) -> dict:
    """
    Extract structured job data from one card element.

    Structure confirmed from debug (emploitunisie.com):

        <div class="last-offers-item">
            <a href="/recherche-jobs-tunisie/...">
                <h3>Job Title</h3>
                <div class="last-offers-details">
                    27.04.2026          ← date (text node)
                    COMPANY NAME        ← company (text node)
                    ...description...
                    Région de : Tunis   ← location
                </div>
            </a>
        </div>

    Args:
        card: BeautifulSoup Tag for one job card.

    Returns:
        dict with keys: source, title, company, location, date, link
    """

    # ── Job title ──────────────────────────────────────────────────
    # Confirmed: job titles are in <h3> with no class
    title = None
    h3 = card.find("h3")
    if h3:
        title = h3.get_text(strip=True)

    # ── Job link ───────────────────────────────────────────────────
    # The entire card is wrapped in an <a> tag
    link = None
    a_tag = card.find("a", href=True)
    if a_tag:
        href = a_tag["href"]
        link = href if href.startswith("http") else "https://www.emploitunisie.com" + href

    # ── Details block: date, company, location ─────────────────────
    # All three live inside div.last-offers-details as text nodes
    date = None
    company = None
    location = None

    details = card.find("div", class_="last-offers-details")
    if details:
        # Get all text segments, stripping whitespace
        # Typical order: [date, company_name, description..., "Région de : X"]
        raw_texts = [
            t.strip() for t in details.stripped_strings
            if t.strip()
        ]

        for text in raw_texts:
            # ── Date: matches DD.MM.YYYY format ───────────────────
            if not date and re.match(r"\d{2}\.\d{2}\.\d{4}", text):
                date = text

            # ── Location: contains "Région de :" ──────────────────
            elif "région" in text.lower() or "region" in text.lower():
                # Strip the "Région de : " prefix to get just the city/region
                location = re.sub(r"(?i)r[eé]gion\s*de\s*:?\s*", "", text).strip()

            # ── Company: uppercase text that isn't the title ───────
            # Company names on this site are ALL CAPS
            elif (
                not company
                and text.isupper()
                and len(text) > 2
                and text != title
            ):
                company = text

        # Fallback company: second text segment if no ALL CAPS found
        if not company and len(raw_texts) > 1:
            # Skip the date (index 0), take next non-location text
            for text in raw_texts[1:]:
                if "région" not in text.lower() and not re.match(r"\d{2}\.\d{2}", text):
                    company = text
                    break

    return {
        "source": "EmploiTunisie",
        "title": title,
        "company": company,
        "location": location,
        "date": date,
        "link": link,
    }


# ─────────────────────────────────────────────────────────────────
# SECTION 9 — DATA CLEANING
# ─────────────────────────────────────────────────────────────────

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply post-scraping cleanup to the raw DataFrame.

    Steps:
        1. Drop exact duplicates (title + company + link)
        2. Strip non-printable / icon characters from text columns
        3. Remove rows with no title AND no link
        4. Normalize date format (DD.MM.YYYY → YYYY-MM-DD)
        5. Reset index

    Args:
        df: Raw DataFrame from scraping.

    Returns:
        Cleaned DataFrame.
    """
    original_count = len(df)

    # ── 1. Deduplicate ─────────────────────────────────────────────
    df.drop_duplicates(subset=["title", "company", "link"], inplace=True)

    # ── 2. Strip non-printable characters ─────────────────────────
    text_cols = ["title", "company", "location", "date"]
    for col in text_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(
                    r"[^\x20-\x7EàâäéèêëîïôùûüçœæÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆ]",
                    "",
                    regex=True,
                )
                .str.strip()
                .replace("nan", None)
            )

    # ── 3. Drop rows with no title and no link ─────────────────────
    df = df[~(df["title"].isna() & df["link"].isna())]

    # ── 4. Normalize date: DD.MM.YYYY → YYYY-MM-DD ────────────────
    def normalize_date(d):
        if pd.isna(d) or not isinstance(d, str):
            return d
        match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", d)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month}-{day}"
        return d

    if "date" in df.columns:
        df["date"] = df["date"].apply(normalize_date)

    # ── 5. Reset index ─────────────────────────────────────────────
    df.reset_index(drop=True, inplace=True)

    log.info(
        "  Cleaning: %d → %d rows (removed %d duplicates/empties)",
        original_count, len(df), original_count - len(df),
    )
    return df


# ─────────────────────────────────────────────────────────────────
# SECTION 10 — MAIN SCRAPING ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────

def scrape_emploitunisie(
    max_pages: int = MAX_PAGES,
    output_path: str = OUTPUT_PATH,
    headless: bool = False,
) -> pd.DataFrame:
    """
    Orchestrate the full emploitunisie.com scraping pipeline.

    Pipeline:
        1. Launch Chrome WebDriver
        2. Scrape homepage (latest jobs section)
        3. Scrape paginated search results (?page=1, 2, ...)
        4. Build DataFrame → clean → save to CSV

    Args:
        max_pages:   Number of paginated result pages to scrape.
        output_path: Destination CSV file path.
        headless:    Run Chrome without a visible window.

    Returns:
        Final cleaned DataFrame.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    driver = setup_driver(headless=headless)
    all_jobs = []
    cookies_accepted = False

    try:
        # ── Step 1: Scrape homepage latest offers ──────────────────
        # The homepage has a "Dernières offres d'emploi" section
        # with div.last-offers-item cards — scrape these first
        log.info("── Homepage ── %s", HOME_URL)
        driver.get(HOME_URL)
        accept_cookies(driver)
        cookies_accepted = True

        content_found = wait_for_content(driver)
        if not content_found:
            log.warning("  ⚠ Homepage content timeout")

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = detect_job_cards(soup)
        if cards:
            page_jobs = [parse_card(card) for card in cards]
            all_jobs.extend(page_jobs)
            log.info("  → %d homepage jobs scraped", len(page_jobs))

        time.sleep(PAGE_DELAY)

        # ── Step 2: Scrape paginated search results ────────────────
        for page in range(1, max_pages + 1):
            url = BASE_URL.format(page)
            log.info("── Page %d/%d ── %s", page, max_pages, url)

            driver.get(url)

            # Cookie consent already handled on homepage
            # but accept again in case of redirect
            if not cookies_accepted:
                accept_cookies(driver)
                cookies_accepted = True

            content_found = wait_for_content(driver)
            if not content_found:
                log.warning("  ⚠ Content timeout on page %d", page)

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Debug: preview to catch blocks or empty pages
            preview = soup.get_text(separator=" ", strip=True)[:200]
            log.debug("  Preview: %r", preview)

            cards = detect_job_cards(soup)
            if not cards:
                log.warning("  ✗ No cards on page %d — stopping early", page)
                break

            page_jobs = [parse_card(card) for card in cards]
            all_jobs.extend(page_jobs)
            log.info(
                "  → %d jobs scraped (running total: %d)",
                len(page_jobs), len(all_jobs),
            )

            if page < max_pages:
                time.sleep(PAGE_DELAY)

    except KeyboardInterrupt:
        log.warning("Interrupted — saving partial results...")

    finally:
        driver.quit()
        log.info("Browser closed")

    # ─────────────────────────────────────────────────────────────
    # SECTION 11 — BUILD, CLEAN & SAVE DATAFRAME
    # ─────────────────────────────────────────────────────────────

    if not all_jobs:
        log.error("No jobs collected. CSV will not be saved.")
        return pd.DataFrame()

    df = pd.DataFrame(all_jobs)
    df = clean_dataframe(df)

    # UTF-8 BOM so Excel opens correctly on Windows
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    log.info("✅ Saved %d jobs to %s", len(df), output_path)

    return df


# ─────────────────────────────────────────────────────────────────
# SECTION 12 — ENTRY POINT
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run with default settings.

    To use as a module:
        from scrape_emploitunisie import scrape_emploitunisie
        df = scrape_emploitunisie(max_pages=10, headless=True)
    """
    df = scrape_emploitunisie(
        max_pages=MAX_PAGES,
        output_path=OUTPUT_PATH,
        headless=False,  # Set True once confirmed working
    )

    if not df.empty:
        print("\n── Sample output (first 5 rows) ──")
        print(df[["title", "company", "location", "date"]].head())