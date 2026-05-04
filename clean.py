"""
clean_jobs.py
─────────────
Cleans raw scraped job data from EmploiTunisie and Keejob,
then produces three ready-for-dashboarding CSV files:
  - cleaned_emploitunisie_jobs.csv
  - cleaned_keejob_jobs.csv
  - cleaned_all_jobs.csv  (combined)

Usage:
    python clean_jobs.py

Expects the two raw files in the same directory (or update INPUT_DIR below).
"""

import re
import pandas as pd
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

INPUT_DIR  = Path("./data")          # folder containing the raw CSVs
OUTPUT_DIR = Path("cleaned")    # folder where cleaned CSVs will be written
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RAW_EMPLOI  = INPUT_DIR / "raw_emploitunisie_jobs.csv"
RAW_KEEJOB  = INPUT_DIR / "raw_keejob_jobs.csv"

OUT_EMPLOI  = OUTPUT_DIR / "cleaned_emploitunisie_jobs.csv"
OUT_KEEJOB  = OUTPUT_DIR / "cleaned_keejob_jobs.csv"
OUT_ALL     = OUTPUT_DIR / "cleaned_all_jobs.csv"


# ── French month map (used for Keejob dates) ─────────────────────────────────

MONTHS_FR = {
    "janvier": 1,  "février": 2,  "mars": 3,    "avril": 4,
    "mai": 5,      "juin": 6,     "juillet": 7,  "août": 8,
    "septembre": 9,"octobre": 10, "novembre": 11,"décembre": 12,
}


# ── Helper functions ──────────────────────────────────────────────────────────

def strip_all(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from every string column."""
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    return df


def parse_fr_date(value: str) -> str:
    """Convert a French date string like '25 avril 2026' to '2026-04-25'."""
    if pd.isna(value):
        return value
    match = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", str(value).strip().lower())
    if match:
        day, month_str, year = int(match.group(1)), match.group(2), int(match.group(3))
        month = MONTHS_FR.get(month_str)
        if month:
            return f"{year}-{month:02d}-{day:02d}"
    return value  # return as-is if pattern doesn't match


def extract_location_from_title(title: str) -> str:
    if pd.isna(title):
        return None
    match = re.search(r"\s*[-–]\s*(.+)$", str(title))
    return match.group(1).strip() if match else None


def remove_location_from_title(title: str) -> str:
    if pd.isna(title):
        return title
    return re.sub(r"\s*[-–]\s*.+$", "", str(title)).strip()


def normalize_keejob_location(location: str) -> str:
    """
    Keejob locations sometimes carry a district + governorate separated by a
    comma and a lot of whitespace, e.g.:
      'La Marsa,                                    Tunis'  →  'La Marsa, Tunis'
    We keep only the governorate (the last token after the last comma) for
    dashboard consistency; comment the return line to keep both parts.
    """
    if pd.isna(location):
        return location
    # Collapse internal whitespace
    cleaned = re.sub(r"\s{2,}", " ", location).strip()
    # Extract governorate (part after the last comma)
    if "," in cleaned:
        governorate = cleaned.split(",")[-1].strip()
        return governorate.title()
    return cleaned.strip().title()


def fix_keejob_apostrophes(title: str) -> str:
    """
    Restore elided apostrophes lost during scraping, e.g.:
      'Agent dEntretien'  →  "Agent d'Entretien"
      'Vente lEnsemble'   →  "Vente l'Ensemble"
    """
    if pd.isna(title):
        return title
    title = re.sub(r"\bd([A-ZÀÂÉÈÊÎÔÙÛÜÇ])", r"d'\1", title)
    title = re.sub(r"\bl([A-ZÀÂÉÈÊÎÔÙÛÜÇ])", r"l'\1", title)
    return title


# ── EmploiTunisie cleaning ────────────────────────────────────────────────────

def clean_emploitunisie(path: Path) -> pd.DataFrame:
    print(f"[EmploiTunisie] Reading {path} …")
    df = pd.read_csv(path)
    initial_rows = len(df)

    # 1. Strip whitespace
    df = strip_all(df)

    # 2. Rows where company/location/date were not scraped:
    #    location is embedded in the title — extract it, then clean the title.
    missing = df["company"].isna()
    df.loc[missing, "location"] = df.loc[missing, "title"].apply(extract_location_from_title)
    df.loc[missing, "title"]    = df.loc[missing, "title"].apply(remove_location_from_title)

    # 3. Normalize location to title-case
    df["location"] = df["location"].str.title()

    # 4. Standardize date to YYYY-MM-DD (already in that format; coerce bad values)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # 5. Title-case company names
    df["company"] = df["company"].str.title()

    # 6. Remove exact duplicates
    before_dedup = len(df)
    df = df.drop_duplicates()
    print(f"[EmploiTunisie] Removed {before_dedup - len(df)} duplicate rows.")

    print(f"[EmploiTunisie] {initial_rows} → {len(df)} rows after cleaning.")
    print(f"[EmploiTunisie] Remaining nulls:\n{df.isna().sum()}\n")
    return df


# ── Keejob cleaning ───────────────────────────────────────────────────────────

def clean_keejob(path: Path) -> pd.DataFrame:
    print(f"[Keejob] Reading {path} …")
    df = pd.read_csv(path)
    initial_rows = len(df)

    # 1. Strip whitespace
    df = strip_all(df)

    # 2. Fix apostrophes in titles lost during scraping
    df["title"] = df["title"].apply(fix_keejob_apostrophes)

    # 3. Normalize location (collapse whitespace, keep governorate)
    df["location"] = df["location"].apply(normalize_keejob_location)

    # 4. Convert French dates to ISO format
    df["date"] = df["date"].apply(parse_fr_date)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # 5. Remove duplicate titles (keep first occurrence)
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["title"])
    print(f"[Keejob] Removed {before_dedup - len(df)} duplicate titles.")

    print(f"[Keejob] {initial_rows} → {len(df)} rows after cleaning.")
    print(f"[Keejob] Remaining nulls:\n{df.isna().sum()}\n")
    return df


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    df_emploi  = clean_emploitunisie(RAW_EMPLOI)
    df_keejob  = clean_keejob(RAW_KEEJOB)

    # Combined dataset
    df_all = pd.concat([df_emploi, df_keejob], ignore_index=True)

    # Save
    df_emploi.to_csv(OUT_EMPLOI, index=False, encoding="utf-8-sig")
    df_keejob.to_csv(OUT_KEEJOB, index=False, encoding="utf-8-sig")
    df_all.to_csv(OUT_ALL,    index=False, encoding="utf-8-sig")

    print("─" * 50)
    print(f"Saved → {OUT_EMPLOI}  ({len(df_emploi)} rows)")
    print(f"Saved → {OUT_KEEJOB}  ({len(df_keejob)} rows)")
    print(f"Saved → {OUT_ALL}     ({len(df_all)} rows, combined)")


if __name__ == "__main__":
    main()