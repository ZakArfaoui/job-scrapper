"""
KEEJOB.COM DEEP JOB SCRAPER
Scrapes listing cards + opens each job page to extract deep-granularity data:
- full description
- responsibilities
- requirements
- skills/tools
- languages
- experience years
- education level
- contract type
- seniority level
Output: data/raw_keejob_jobs_deep.csv
"""

import os
import re
import time
import logging
from typing import Dict, List, Optional

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://www.keejob.com/offres-emploi/?page={}"
OUTPUT_PATH = "data/raw_keejob_jobs_deep.csv"
MAX_PAGES = 50
PAGE_DELAY = 4
DETAIL_DELAY = 1
CONTENT_TIMEOUT = 10
SCRAPE_DETAILS = True

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

SKILL_PATTERNS = {
    "python": r"\bpython\b", "java": r"\bjava\b", "javascript": r"\bjavascript\b|\bjs\b",
    "typescript": r"\btypescript\b|\bts\b", "php": r"\bphp\b", "c#": r"\bc#\b|\.net",
    "c++": r"\bc\+\+\b", "sql": r"\bsql\b", "mysql": r"\bmysql\b", "postgresql": r"\bpostgresql\b|\bpostgres\b",
    "oracle": r"\boracle\b", "mongodb": r"\bmongodb\b|\bmongo\b", "html/css": r"\bhtml\b|\bcss\b",
    "react": r"\breact\b|reactjs", "angular": r"\bangular\b", "vue": r"\bvue\b|vuejs",
    "node.js": r"\bnode\.js\b|\bnodejs\b", "spring": r"\bspring\b|spring boot", "laravel": r"\blaravel\b",
    "django": r"\bdjango\b", "flask": r"\bflask\b", "docker": r"\bdocker\b", "kubernetes": r"\bkubernetes\b|\bk8s\b",
    "git": r"\bgit\b|github|gitlab", "linux": r"\blinux\b", "aws": r"\baws\b|amazon web services",
    "azure": r"\bazure\b", "gcp": r"\bgcp\b|google cloud", "devops": r"\bdevops\b", "ci/cd": r"\bci/cd\b|jenkins|gitlab ci",
    "power bi": r"power\s*bi", "tableau": r"\btableau\b", "excel": r"\bexcel\b", "erp": r"\berp\b", "sap": r"\bsap\b",
    "crm": r"\bcrm\b|salesforce", "seo": r"\bseo\b", "digital marketing": r"marketing digital|digital marketing",
    "machine learning": r"machine learning|apprentissage automatique", "deep learning": r"deep learning|apprentissage profond",
    "data analysis": r"data analysis|analyse de donn[ée]es|data analyst", "cybersecurity": r"cybersecurity|cybers[ée]curit[ée]|sécurité informatique",
    "communication": r"communication", "teamwork": r"travail en [ée]quipe|teamwork|esprit d['’]?équipe", "leadership": r"leadership",
    "problem solving": r"problem solving|résolution de problèmes|analyse et synthèse", "project management": r"gestion de projet|project management",
}

LANGUAGE_PATTERNS = {
    "french": r"fran[çc]ais", "english": r"anglais|english", "arabic": r"arabe|arabic", "italian": r"italien|italian", "german": r"allemand|german", "spanish": r"espagnol|spanish"
}

EDUCATION_PATTERNS = {
    "Bac": r"\bbac\b|baccalaur[ée]at", "Bac+2": r"bac\s*\+\s*2|bts|dut|technicien sup[ée]rieur",
    "Bac+3": r"bac\s*\+\s*3|licence", "Bac+4": r"bac\s*\+\s*4|ma[iî]trise",
    "Bac+5": r"bac\s*\+\s*5|master|ing[ée]nieur|mast[èe]re", "PhD": r"doctorat|phd"
}

CONTRACT_PATTERNS = {
    "CDI": r"\bcdi\b", "CDD": r"\bcdd\b", "SIVP": r"\bsivp\b", "Freelance": r"freelance|ind[ée]pendant",
    "Internship": r"stage|internship|stagiaire", "Part-time": r"temps partiel|part[- ]time", "Full-time": r"plein temps|full[- ]time|temps plein"
}

SENIORITY_PATTERNS = {
    "Internship": r"stage|stagiaire|internship", "Junior": r"junior|d[ée]butant|0\s*[àa-]\s*2 ans",
    "Mid-level": r"confirm[ée]|2\s*[àa-]\s*5 ans|3\s*[àa-]\s*5 ans", "Senior": r"senior|exp[ée]riment[ée]|5\+|plus de 5 ans|lead|manager"
}

SECTION_KEYWORDS = {
    "requirements": ["profil recherché", "exigences", "compétences requises", "qualifications", "requirements", "profile"],
    "responsibilities": ["missions", "responsabilités", "tâches", "description du poste", "responsibilities", "mission"],
}


def setup_driver(headless: bool = False) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"user-agent={USER_AGENT}")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})
    return driver


def accept_cookies(driver: webdriver.Chrome, timeout: int = 5) -> None:
    xpath = "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accepter') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continuer') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'valider') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok')]"
    try:
        WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()
        time.sleep(1)
    except Exception:
        pass


def wait_for_listing_content(driver: webdriver.Chrome, timeout: int = CONTENT_TIMEOUT) -> bool:
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div h6, div h5, article h3, div h4")))
        return True
    except Exception:
        return False


def wait_for_detail_content(driver: webdriver.Chrome, timeout: int = CONTENT_TIMEOUT) -> bool:
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        return True
    except Exception:
        return False


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def unique_sorted(values: List[str]) -> str:
    return ", ".join(sorted(set(v for v in values if v)))


def extract_matches(text: str, patterns: Dict[str, str]) -> str:
    lower = text.lower()
    found = [label for label, pattern in patterns.items() if re.search(pattern, lower, re.IGNORECASE)]
    return unique_sorted(found)


def extract_experience_years(text: str) -> str:
    patterns = [
        r"(\d+)\s*[àa-]\s*(\d+)\s*ans",
        r"minimum\s*(\d+)\s*ans",
        r"au moins\s*(\d+)\s*ans",
        r"(\d+)\+\s*ans",
        r"(\d+)\s*ans\s+d['’]?exp[ée]rience",
        r"experience\s*[:\-]?\s*(\d+)\s*ans",
    ]
    hits = []
    for pat in patterns:
        for match in re.finditer(pat, text.lower(), re.IGNORECASE):
            hits.append(match.group(0))
    return unique_sorted(hits)


def infer_job_category(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    categories = {
        "IT & Software": r"developer|développeur|software|web|data|python|java|react|angular|devops|informatique|it|cyber",
        "Sales & Marketing": r"commercial|vente|sales|marketing|communication|business developer|client|crm",
        "Finance & Accounting": r"finance|comptable|audit|contrôle de gestion|fiscal|trésor|banque",
        "HR": r"ressources humaines|recrutement|paie|talent|formation|\brh\b",
        "Engineering & Industry": r"ingénieur|génie|maintenance|production|qualité|hse|mécanique|électrique|industriel",
        "Logistics & Supply Chain": r"logistique|supply chain|achat|approvisionnement|stock|transport",
        "Admin & Legal": r"assistant|administratif|secrétaire|juriste|droit|office manager",
        "Healthcare": r"médecin|infirmier|pharmacien|santé|médical",
        "Education": r"enseignant|formateur|professeur|pédagogique",
    }
    for cat, pat in categories.items():
        if re.search(pat, text, re.IGNORECASE):
            return cat
    return "Other"


def split_sections(text: str) -> Dict[str, str]:
    result = {"requirements": "", "responsibilities": ""}
    if not text:
        return result
    parts = re.split(r"(?=\b(?:Profil recherché|Exigences|Compétences requises|Qualifications|Missions|Responsabilités|Tâches|Description du poste|Requirements|Responsibilities)\b)", text, flags=re.IGNORECASE)
    for part in parts:
        low = part.lower()
        for target, keys in SECTION_KEYWORDS.items():
            if any(k in low[:100] for k in keys):
                result[target] = normalize_text(part)
    return result


def detect_job_cards(soup: BeautifulSoup) -> list:
    strategies = [
        lambda s: s.find_all("div", class_="block_white_a"),
        lambda s: s.find_all("div", class_=lambda c: c and "job" in c.lower()),
        lambda s: s.find_all("article"),
        lambda s: s.find_all("div", class_=lambda c: c and "offer" in c.lower()),
        lambda s: s.find_all("div", class_=lambda c: c and "card" in c.lower()),
        lambda s: s.find_all("li", class_=lambda c: c and "offer" in c.lower()),
    ]
    for strategy in strategies:
        cards = strategy(soup)
        if cards:
            return cards
    return [div for div in soup.find_all("div") if div.find(["h2", "h3", "h4", "h5", "h6"]) and div.find("a", href=True)]


def parse_card(card) -> dict:
    title_tag = card.find(["h2", "h3", "h4", "h5", "h6"])
    title = normalize_text(title_tag.get_text(" ", strip=True)) if title_tag else None

    company_tag = card.find("a", class_="text-primary")
    company = normalize_text(company_tag.get_text(" ", strip=True)) if company_tag else None

    location = None
    loc_icon = card.find("i", class_=lambda c: c and "map" in c)
    if loc_icon and loc_icon.parent:
        location = normalize_text(loc_icon.parent.get_text(" ", strip=True))

    date = None
    date_icon = card.find("i", class_=lambda c: c and "clock" in c)
    if date_icon and date_icon.parent:
        date = normalize_text(date_icon.parent.get_text(" ", strip=True))

    link = None
    link_tag = card.find("a", href=True)
    if link_tag:
        href = link_tag["href"]
        link = href if href.startswith("http") else "https://www.keejob.com" + href

    return {"source": "Keejob", "title": title, "company": company, "location": location, "date": date, "link": link}


def extract_detail_text(soup: BeautifulSoup) -> str:
    for unwanted in soup.select("script, style, nav, header, footer, aside, form"):
        unwanted.decompose()
    candidates = []
    selectors = [
        "article", ".job-description", ".content", ".page-content", ".offer", ".block_white_a",
        "div[class*='description']", "div[class*='job']", "div[class*='offer']", "main"
    ]
    for selector in selectors:
        for tag in soup.select(selector):
            txt = normalize_text(tag.get_text(" ", strip=True))
            if len(txt) > 250:
                candidates.append(txt)
    if candidates:
        return max(candidates, key=len)
    return normalize_text(soup.get_text(" ", strip=True))


def enrich_job_details(driver: webdriver.Chrome, job: dict) -> dict:
    empty = {
        "description": "", "responsibilities": "", "requirements": "", "skills": "", "languages": "",
        "experience_years": "", "education_level": "", "contract_type": "", "seniority_level": "",
        "job_category": infer_job_category(job.get("title", ""), ""), "detail_scrape_status": "not_requested",
    }
    link = job.get("link")
    if not SCRAPE_DETAILS or not link:
        return empty
    try:
        driver.get(link)
        wait_for_detail_content(driver)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        description = extract_detail_text(soup)
        sections = split_sections(description)
        return {
            "description": description,
            "responsibilities": sections["responsibilities"],
            "requirements": sections["requirements"],
            "skills": extract_matches(description, SKILL_PATTERNS),
            "languages": extract_matches(description, LANGUAGE_PATTERNS),
            "experience_years": extract_experience_years(description),
            "education_level": extract_matches(description, EDUCATION_PATTERNS),
            "contract_type": extract_matches(description, CONTRACT_PATTERNS),
            "seniority_level": extract_matches(description, SENIORITY_PATTERNS),
            "job_category": infer_job_category(job.get("title", ""), description),
            "detail_scrape_status": "ok" if description else "empty",
        }
    except Exception as exc:
        log.warning("Detail scrape failed for %s: %s", link, exc)
        empty["detail_scrape_status"] = "failed"
        return empty


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    original = len(df)
    df = df.drop_duplicates(subset=["title", "company", "link"])
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.replace(r"[^\x20-\x7EàâäéèêëîïôùûüçœæÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆ\n]", "", regex=True).str.strip().replace("nan", None)
    df = df[~(df["title"].isna() & df["link"].isna())].reset_index(drop=True)
    log.info("Cleaning: %d → %d rows", original, len(df))
    return df


def scrape_keejob(max_pages: int = MAX_PAGES, output_path: str = OUTPUT_PATH, headless: bool = False, scrape_details: bool = True) -> pd.DataFrame:
    global SCRAPE_DETAILS
    SCRAPE_DETAILS = scrape_details
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    driver = setup_driver(headless=headless)
    all_jobs = []
    cookies_accepted = False
    try:
        for page in range(1, max_pages + 1):
            url = BASE_URL.format(page)
            log.info("── Page %d/%d ── %s", page, max_pages, url)
            driver.get(url)
            if not cookies_accepted:
                accept_cookies(driver)
                cookies_accepted = True
            wait_for_listing_content(driver)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            cards = detect_job_cards(soup)
            if not cards:
                log.warning("No cards found on page %d. Stopping.", page)
                break
            page_jobs = [parse_card(card) for card in cards]
            log.info("Found %d listing cards", len(page_jobs))
            for i, job in enumerate(page_jobs, start=1):
                if job.get("link"):
                    log.info("  Detail %d/%d: %s", i, len(page_jobs), job.get("title"))
                    job.update(enrich_job_details(driver, job))
                    time.sleep(DETAIL_DELAY)
                all_jobs.append(job)
            time.sleep(PAGE_DELAY)
    except KeyboardInterrupt:
        log.warning("Interrupted — saving partial results.")
    finally:
        driver.quit()

    if not all_jobs:
        return pd.DataFrame()
    df = clean_dataframe(pd.DataFrame(all_jobs))
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    log.info("Saved %d deep jobs to %s", len(df), output_path)
    return df


if __name__ == "__main__":
    df = scrape_keejob(max_pages=MAX_PAGES, output_path=OUTPUT_PATH, headless=False, scrape_details=True)
    if not df.empty:
        print(df[["title", "company", "location", "skills", "languages", "experience_years", "education_level", "contract_type"]].head())
