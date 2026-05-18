import re
import ast
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
OUTPUT_DIR = Path("cleaned")
OUTPUT_DIR.mkdir(exist_ok=True)

INPUT_FILES = {
    "EmploiTunisie": DATA_DIR / "raw_emploitunisie_jobs_deep.csv",
    "Keejob": DATA_DIR / "raw_keejob_jobs_deep.csv",
}

OUT_ALL = OUTPUT_DIR / "cleaned_all_jobs_deep.csv"
OUT_SKILLS = OUTPUT_DIR / "skills_long_format.csv"


def clean_text(x):
    if pd.isna(x):
        return ""
    x = str(x)
    x = re.sub(r"<.*?>", " ", x)
    x = re.sub(r"\s+", " ", x)
    x = x.strip()
    if x.lower() in ["nan", "none", "null"]:
        return ""
    return x


def parse_list_column(x):
    if pd.isna(x) or str(x).strip() == "":
        return []

    x = str(x).strip()

    try:
        value = ast.literal_eval(x)
        if isinstance(value, list):
            return [clean_text(v).lower() for v in value if clean_text(v)]
    except Exception:
        pass

    parts = re.split(r"[,;|/]", x)
    return sorted(set(clean_text(p).lower() for p in parts if clean_text(p)))


def normalize_location(x):
    x = clean_text(x)
    if not x:
        return "Unknown"
    if "," in x:
        x = x.split(",")[-1]
    return x.strip().title()


def normalize_contract(x):
    x = clean_text(x).lower()
    if not x:
        return "Unknown"
    if "cdi" in x:
        return "CDI"
    if "cdd" in x:
        return "CDD"
    if "stage" in x or "intern" in x:
        return "Internship"
    if "freelance" in x:
        return "Freelance"
    if "temps partiel" in x or "part time" in x:
        return "Part-time"
    if "temps plein" in x or "full time" in x:
        return "Full-time"
    return x.title()


def extract_experience(text):
    text = clean_text(text).lower()
    patterns = [
        r"(\d+)\s*(?:ans|years|year)",
        r"expérience\s*[:\-]?\s*(\d+)",
        r"experience\s*[:\-]?\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    return None


def normalize_seniority(title, description):
    text = f"{title} {description}".lower()

    if any(w in text for w in ["junior", "débutant", "debutant", "entry"]):
        return "Junior"
    if any(w in text for w in ["senior", "expert", "lead", "manager"]):
        return "Senior"
    if any(w in text for w in ["confirmé", "confirme", "mid"]):
        return "Mid-Level"

    return "Unknown"


def categorize(title, description):
    text = f"{title} {description}".lower()

    categories = {
        "IT & Dev": r"python|java|javascript|react|angular|php|sql|data|developer|développeur|web|software|devops|cloud|cyber",
        "Finance": r"finance|comptable|audit|fiscal|banque|bank|accounting",
        "Sales & Marketing": r"commercial|vente|sales|marketing|communication|crm|business",
        "HR": r"ressources humaines|recrutement|rh|talent|paie",
        "Engineering": r"ingénieur|engineer|maintenance|production|qualité|industrial|électrique|mécanique",
        "Logistics": r"logistique|supply chain|achat|transport|stock|warehouse",
        "Admin & Legal": r"assistant|administratif|juriste|legal|secrétaire",
        "Healthcare": r"santé|medical|médecin|pharmacien|infirmier",
        "Education": r"enseignant|professeur|formateur|teacher|training",
    }

    for cat, pattern in categories.items():
        if re.search(pattern, text):
            return cat

    return "Other"


def clean_file(path, source_name):
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower()

    required_cols = [
        "source", "title", "company", "location", "date", "link",
        "description", "responsibilities", "requirements",
        "skills", "languages", "experience_years",
        "education_level", "contract_type",
        "seniority_level", "job_category",
        "detail_scrape_status"
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    df["source"] = source_name

    text_cols = [
        "title", "company", "location", "link",
        "description", "responsibilities", "requirements",
        "education_level", "detail_scrape_status"
    ]

    for col in text_cols:
        df[col] = df[col].apply(clean_text)

    df["location"] = df["location"].apply(normalize_location)
    df["company"] = df["company"].replace("", "Unknown")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df["skills_list"] = df["skills"].apply(parse_list_column)
    df["languages_list"] = df["languages"].apply(parse_list_column)

    df["skills"] = df["skills_list"].apply(lambda x: ", ".join(x))
    df["languages"] = df["languages_list"].apply(lambda x: ", ".join(x))

    combined_text = (
        df["title"].fillna("") + " " +
        df["description"].fillna("") + " " +
        df["requirements"].fillna("")
    )

    df["experience_years"] = pd.to_numeric(df["experience_years"], errors="coerce")
    missing_exp = df["experience_years"].isna()
    df.loc[missing_exp, "experience_years"] = combined_text[missing_exp].apply(extract_experience)

    df["contract_type"] = df["contract_type"].apply(normalize_contract)

    df["seniority_level"] = df.apply(
        lambda row: normalize_seniority(row["title"], row["description"]),
        axis=1
    )

    df["job_category"] = df.apply(
        lambda row: categorize(row["title"], row["description"]),
        axis=1
    )

    df["num_skills"] = df["skills_list"].apply(len)

    df = df.drop_duplicates(subset=["title", "company", "location", "source"])

    return df


all_dfs = []

for source_name, path in INPUT_FILES.items():
    if path.exists():
        print(f"Cleaning {source_name}: {path}")
        df = clean_file(path, source_name)
        all_dfs.append(df)
        df.to_csv(OUTPUT_DIR / f"cleaned_{source_name.lower()}_jobs_deep.csv", index=False, encoding="utf-8-sig")
    else:
        print(f"Missing file: {path}")

if not all_dfs:
    raise FileNotFoundError("No input files found in data/ folder.")

combined = pd.concat(all_dfs, ignore_index=True)

combined = combined.drop_duplicates(
    subset=["title", "company", "location", "source"]
)

combined.to_csv(OUT_ALL, index=False, encoding="utf-8-sig")

skills_rows = []

for _, row in combined.iterrows():
    for skill in row["skills_list"]:
        skills_rows.append({
            "title": row["title"],
            "company": row["company"],
            "location": row["location"],
            "source": row["source"],
            "job_category": row["job_category"],
            "skill": skill
        })

skills_df = pd.DataFrame(skills_rows)
skills_df.to_csv(OUT_SKILLS, index=False, encoding="utf-8-sig")

print("\nCleaning finished.")
print(f"Combined dataset saved to: {OUT_ALL}")
print(f"Skills dataset saved to: {OUT_SKILLS}")
print(f"Total jobs: {len(combined)}")
print(f"Total skill rows: {len(skills_df)}")