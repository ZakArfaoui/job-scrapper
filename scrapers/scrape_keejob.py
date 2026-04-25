"""
╔══════════════════════════════════════════════════════════════════╗
║              KEEJOB.COM JOB SCRAPER                              ║
║  Scrapes job listings from https://www.keejob.com/offres-emploi/ ║
║  Output: data/raw_keejob_jobs.csv                                ║
╚══════════════════════════════════════════════════════════════════╝

Dependencies:
    pip install selenium webdriver-manager beautifulsoup4 pandas
"""

# ─────────────────────────────────────────────────────────────────
# SECTION 1 — IMPORTS
# ─────────────────────────────────────────────────────────────────
import os
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

# Base URL — {page} is replaced with the page number at runtime
BASE_URL = "https://www.keejob.com/offres-emploi/?page={}"

# Where to save the final CSV
OUTPUT_PATH = "data/raw_keejob_jobs.csv"

# How many pages to scrape (each page ~15 jobs)
MAX_PAGES = 20

# Seconds to wait between page requests (be polite to the server)
PAGE_DELAY = 4

# Seconds to wait for dynamic content to load before giving up
CONTENT_TIMEOUT = 10

# Realistic browser User-Agent to avoid bot detection
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ─────────────────────────────────────────────────────────────────
# SECTION 3 — LOGGING SETUP
# ─────────────────────────────────────────────────────────────────

# Configure a simple logger so every step is traceable in the console
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
    Initialize and return a Selenium Chrome WebDriver with anti-detection
    measures applied.

    Args:
        headless: Run browser without a visible window. Set True for
                  servers/cron jobs once you've confirmed it works visually.

    Returns:
        A configured Chrome WebDriver instance.
    """
    options = Options()

    # ── Headless mode (no visible browser window) ──────────────────
    if headless:
        options.add_argument("--headless=new")   # "new" headless is less detectable than legacy

    # ── Window & environment flags ─────────────────────────────────
    options.add_argument("--start-maximized")        # Maximized window looks more human
    options.add_argument("--no-sandbox")             # Required in some Linux/Docker environments
    options.add_argument("--disable-dev-shm-usage")  # Prevents crashes in low-memory environments

    # ── Anti-bot-detection flags ───────────────────────────────────
    # Tells Chrome NOT to announce itself as an automated browser
    options.add_argument("--disable-blink-features=AutomationControlled")
    # Remove "Chrome is being controlled by automated software" banner
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # Disable the ChromeDriver extension that sites can detect
    options.add_experimental_option("useAutomationExtension", False)
    # Spoof a real browser User-Agent string
    options.add_argument(f"user-agent={USER_AGENT}")

    # ── Launch Chrome ──────────────────────────────────────────────
    # ChromeDriverManager auto-downloads the correct ChromeDriver version
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    # ── Patch navigator.webdriver via Chrome DevTools Protocol ─────
    # Many sites check window.navigator.webdriver in JS; this hides it
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
    Detect and click a cookie consent / GDPR banner if one appears.
    Keejob explicitly requires cookies to be enabled — without accepting,
    the page returns an empty shell with no job listings.

    Looks for buttons whose text contains common consent words in French/English:
    'accepter', 'accept', 'agree', 'ok', 'continuer', 'valider'.

    Args:
        driver:  Active WebDriver session.
        timeout: Seconds to wait for the banner to appear before giving up.
    """
    # XPath that matches buttons containing any consent-related word
    # translate() is used to do a case-insensitive comparison in XPath 1.0
    consent_xpath = (
        "//button["
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accepter') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continuer') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'valider') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok')"
        "]"
    )

    try:
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, consent_xpath))
        )
        btn.click()
        log.info("  ✓ Cookie consent accepted")
        time.sleep(1)  # Brief pause for the banner animation to close
    except Exception:
        # No banner found — either already accepted or site doesn't show one
        log.info("  ℹ No cookie banner detected")


# ─────────────────────────────────────────────────────────────────
# SECTION 6 — DYNAMIC CONTENT WAIT
# ─────────────────────────────────────────────────────────────────

def wait_for_content(driver: webdriver.Chrome, timeout: int = CONTENT_TIMEOUT) -> bool:
    """
    Wait until job listing content appears in the DOM.
    This is safer than time.sleep() because it adapts to network speed:
    - Returns immediately once content is found
    - Gives up after `timeout` seconds if nothing loads

    We look for any heading tag (<h5>, <h6>) inside a <div>, which is
    the common pattern for job card titles on Keejob.

    Args:
        driver:  Active WebDriver session.
        timeout: Maximum seconds to wait.

    Returns:
        True if content was found, False if it timed out.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div h6, div h5, article h3, div h4")
            )
        )
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────
# SECTION 7 — JOB CARD DETECTION (multi-strategy)
# ─────────────────────────────────────────────────────────────────

def detect_job_cards(soup: BeautifulSoup) -> list:
    """
    Attempt to locate job listing cards in the parsed HTML using multiple
    CSS selector strategies, from most specific to most generic.

    Why multiple strategies?
        Websites redesign frequently. Hard-coding a single class name
        (e.g. "block_white_a") breaks silently when the site updates.
        This function tries 6 approaches and reports which one succeeded,
        making future debugging much easier.

    Args:
        soup: BeautifulSoup object of the page HTML.

    Returns:
        A list of Tag objects representing individual job cards.
        Returns an empty list if nothing is found.
    """

    strategies = [
        # Strategy 0 — Original class name (may be outdated after site redesigns)
        ("Original class 'block_white_a'",
         lambda s: s.find_all("div", class_="block_white_a")),

        # Strategy 1 — Any div whose class contains the word "job"
        ("Div with 'job' in class",
         lambda s: s.find_all("div", class_=lambda c: c and "job" in c.lower())),

        # Strategy 2 — HTML5 <article> tags (semantic job cards)
        ("Article tags",
         lambda s: s.find_all("article")),

        # Strategy 3 — Any div whose class contains "offer"
        ("Div with 'offer' in class",
         lambda s: s.find_all("div", class_=lambda c: c and "offer" in c.lower())),

        # Strategy 4 — Any div whose class contains "card"
        ("Div with 'card' in class",
         lambda s: s.find_all("div", class_=lambda c: c and "card" in c.lower())),

        # Strategy 5 — <li> elements whose class contains "offer"
        ("Li with 'offer' in class",
         lambda s: s.find_all("li", class_=lambda c: c and "offer" in (c or "").lower())),
    ]

    for name, strategy in strategies:
        cards = strategy(soup)
        if cards:
            log.info("  ✓ Selector strategy matched: '%s' → %d card(s)", name, len(cards))
            return cards

    # ── Heuristic fallback ─────────────────────────────────────────
    # If none of the above work, find any <div> that contains both a
    # heading tag AND a link — the minimum structure of a job card
    fallback = [
        div for div in soup.find_all("div")
        if div.find(["h2", "h3", "h4", "h5", "h6"]) and div.find("a", href=True)
    ]
    log.warning("  ⚠ All strategies failed. Heuristic fallback found %d candidate(s)", len(fallback))
    return fallback


# ─────────────────────────────────────────────────────────────────
# SECTION 8 — SINGLE CARD PARSER
# ─────────────────────────────────────────────────────────────────

def parse_card(card) -> dict:
    """
    Extract structured job data from a single job card HTML element.

    Fields extracted:
        - title:    Job title (from the first heading tag found)
        - company:  Employer name (from <a class="text-primary">)
        - location: City/region (from the element next to a map-marker icon)
        - date:     Posting date (from the element next to a clock icon)
        - link:     Full URL to the job detail page

    Args:
        card: A BeautifulSoup Tag object for one job card.

    Returns:
        A dict with keys: source, title, company, location, date, link.
        Any field that cannot be found is set to None.
    """

    # ── Job title ──────────────────────────────────────────────────
    # Try heading tags from h2 down to h6; use the first one found
    title_tag = card.find(["h2", "h3", "h4", "h5", "h6"])
    title = title_tag.get_text(strip=True) if title_tag else None

    # ── Company name ───────────────────────────────────────────────
    # Keejob marks the company link with class "text-primary"
    company_tag = card.find("a", class_="text-primary")
    company = company_tag.get_text(strip=True) if company_tag else None

    # ── Location ───────────────────────────────────────────────────
    # The location is displayed next to a Font Awesome map-marker icon.
    # We find the <i> icon, then grab the text from its parent element.
    location = None
    loc_icon = card.find("i", class_=lambda c: c and "map" in c)
    if loc_icon and loc_icon.parent:
        # Strip leading whitespace that may appear after the icon
        location = loc_icon.parent.get_text(strip=True)

    # ── Posting date ───────────────────────────────────────────────
    # Same pattern: clock icon → parent element text
    date = None
    date_icon = card.find("i", class_=lambda c: c and "clock" in c)
    if date_icon and date_icon.parent:
        date = date_icon.parent.get_text(strip=True)

    # ── Job detail link ────────────────────────────────────────────
    # Use the first <a href> found in the card.
    # If the href is relative (starts with /), prepend the base domain.
    link = None
    link_tag = card.find("a", href=True)
    if link_tag:
        href = link_tag["href"]
        link = href if href.startswith("http") else "https://www.keejob.com" + href

    return {
        "source": "Keejob",
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
        1. Drop fully duplicate rows (same title + company + link)
        2. Strip icon artifacts from location/date strings
           (Font Awesome icons sometimes leave non-printable chars)
        3. Remove rows with no title AND no link (unusable records)
        4. Reset the index so it's sequential after deduplication

    Args:
        df: Raw DataFrame from scraping.

    Returns:
        Cleaned DataFrame.
    """

    original_count = len(df)

    # ── 1. Remove exact duplicates ─────────────────────────────────
    df.drop_duplicates(subset=["title", "company", "link"], inplace=True)

    # ── 2. Strip non-ASCII / icon artifacts from text fields ───────
    # Font Awesome icons can inject characters like \uf041 (map marker)
    # into the parent element's text. This regex removes non-printable chars.
    for col in ["location", "date", "title", "company"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(r"[^\x20-\x7EàâäéèêëîïôùûüçœæÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆ]", "", regex=True)
                .str.strip()
                .replace("nan", None)  # Convert string "nan" back to None
            )

    # ── 3. Drop rows with no title and no link (not useful) ────────
    df = df[~(df["title"].isna() & df["link"].isna())]

    # ── 4. Reset index ─────────────────────────────────────────────
    df.reset_index(drop=True, inplace=True)

    log.info("  Cleaning: %d → %d rows (removed %d duplicates/empties)",
             original_count, len(df), original_count - len(df))
    return df


# ─────────────────────────────────────────────────────────────────
# SECTION 10 — MAIN SCRAPING ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────

def scrape_keejob(
    max_pages: int = MAX_PAGES,
    output_path: str = OUTPUT_PATH,
    headless: bool = False,
) -> pd.DataFrame:
    """
    Main entry point: orchestrates the full scraping pipeline.

    Pipeline:
        1. Launch Chrome WebDriver
        2. For each page:
            a. Load the URL
            b. Accept cookie banner (first page only)
            c. Wait for job content to render
            d. Parse the HTML and extract job cards
            e. Parse each card into a structured dict
        3. Build a DataFrame, clean it, save to CSV

    Args:
        max_pages:   Number of pages to scrape.
        output_path: File path for the output CSV.
        headless:    Whether to run Chrome without a visible window.

    Returns:
        The final cleaned DataFrame.
    """

    # ── Ensure output directory exists ────────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    driver = setup_driver(headless=headless)
    all_jobs = []          # Accumulates raw job dicts across all pages
    cookies_accepted = False  # Track whether we've already clicked the banner

    try:
        for page in range(1, max_pages + 1):
            url = BASE_URL.format(page)
            log.info("── Page %d/%d ── %s", page, max_pages, url)

            # ── Load the page ──────────────────────────────────────
            driver.get(url)

            # ── Accept cookie consent (first page only) ────────────
            # The session carries the cookie forward to subsequent pages
            if not cookies_accepted:
                accept_cookies(driver)
                cookies_accepted = True

            # ── Wait for dynamic JS content to render ─────────────
            content_found = wait_for_content(driver)
            if not content_found:
                log.warning("  ⚠ Content timeout on page %d — possible block or empty page", page)

            # ── Parse rendered HTML with BeautifulSoup ─────────────
            # We use driver.page_source (the fully-rendered DOM),
            # NOT requests.get() which only returns the raw HTML before JS runs
            soup = BeautifulSoup(driver.page_source, "html.parser")

            # ── Debug: preview first 300 chars of page text ────────
            # Useful to spot cookie walls, CAPTCHAs, or redirect pages
            preview = soup.get_text(separator=" ", strip=True)[:300]
            log.debug("  Page text preview: %r", preview)

            # ── Detect job card elements ───────────────────────────
            cards = detect_job_cards(soup)
            if not cards:
                log.warning("  ✗ No cards found on page %d — stopping early", page)
                break

            # ── Parse each card into a structured dict ─────────────
            page_jobs = [parse_card(card) for card in cards]
            all_jobs.extend(page_jobs)
            log.info("  → Scraped %d jobs (running total: %d)", len(page_jobs), len(all_jobs))

            # ── Polite delay before next request ──────────────────
            if page < max_pages:
                time.sleep(PAGE_DELAY)

    except KeyboardInterrupt:
        # Allow Ctrl+C to abort early and still save whatever was collected
        log.warning("Interrupted by user — saving partial results...")

    finally:
        # Always quit the browser, even if an exception occurred
        driver.quit()
        log.info("Browser closed")

    # ─────────────────────────────────────────────────────────────
    # SECTION 11 — BUILD, CLEAN & SAVE DATAFRAME
    # ─────────────────────────────────────────────────────────────

    if not all_jobs:
        log.error("No jobs were collected. CSV will not be saved.")
        return pd.DataFrame()

    # Build the DataFrame from list of dicts
    df = pd.DataFrame(all_jobs)

    # Apply cleaning steps (dedup, strip artifacts, drop empty rows)
    df = clean_dataframe(df)

    # Save to CSV with UTF-8 BOM (utf-8-sig) so Excel opens it correctly
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    log.info("✅ Saved %d jobs to %s", len(df), output_path)

    return df


# ─────────────────────────────────────────────────────────────────
# SECTION 12 — ENTRY POINT
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run the scraper directly with default settings.

    To customize, edit the constants in SECTION 2, or import and call
    scrape_keejob() with arguments from another script:

        from scrape_keejob import scrape_keejob
        df = scrape_keejob(max_pages=10, headless=True)
    """
    df = scrape_keejob(
        max_pages=MAX_PAGES,
        output_path=OUTPUT_PATH,
        headless=False,   # Set True once confirmed working
    )

    # Optional: quick preview of results in terminal
    if not df.empty:
        print("\n── Sample output (first 5 rows) ──")
        print(df[["title", "company", "location", "date"]].head())