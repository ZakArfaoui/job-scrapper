import re
import ast
from pathlib import Path
from itertools import combinations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Tunisia HR Talent Intelligence",
    page_icon="🧭",
    layout="wide"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {font-family: 'Inter', sans-serif !important;}
.stApp {background: #F6F8FB; color: #0F172A;}
.block-container {padding-top: 1.2rem; max-width: 1500px;}
#MainMenu, footer, header {visibility: hidden;}
[data-testid="stSidebar"] {background: #FFFFFF; border-right: 1px solid #E5E7EB;}
.hero {background: linear-gradient(135deg,#0B1220 0%,#172554 50%,#2563EB 100%); padding: 1.6rem 1.8rem; border-radius: 24px; color:white; margin-bottom:1rem; box-shadow:0 18px 38px rgba(15,23,42,.18)}
.hero h1 {font-size:2rem; margin:0; letter-spacing:-.04em; font-weight:800;}
.hero p {max-width:920px; color:rgba(255,255,255,.80); margin:.55rem 0 0; font-size:.95rem; line-height:1.55;}
.pill {display:inline-block; padding:.35rem .72rem; border-radius:999px; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.20); margin-right:.4rem; margin-top:.75rem; font-size:.75rem; font-weight:700; color:rgba(255,255,255,.92)}
.section-title {font-size:1.05rem; font-weight:800; margin-top:1.25rem; margin-bottom:.15rem; color:#111827;}
.section-caption {font-size:.82rem; color:#64748B; margin-bottom:.8rem;}
.kpi-card {background:white; border:1px solid #E5E7EB; border-radius:18px; padding:1rem 1.05rem; min-height:132px; box-shadow:0 1px 2px rgba(16,24,40,.05)}
.kpi-label {font-size:.68rem; color:#64748B; text-transform:uppercase; letter-spacing:.08em; font-weight:800;}
.kpi-value {font-size:1.75rem; line-height:1.1; margin-top:.45rem; font-weight:800; color:#0F172A;}
.kpi-note {font-size:.75rem; color:#64748B; margin-top:.45rem; line-height:1.35;}
.insight-card {background:white; border:1px solid #E5E7EB; border-radius:18px; padding:1rem 1.1rem; box-shadow:0 1px 2px rgba(16,24,40,.05)}
.insight-title {font-size:.85rem; font-weight:800; color:#0F172A; margin-bottom:.35rem;}
.insight-text {font-size:.83rem; color:#475569; line-height:1.5;}
[data-testid="stPlotlyChart"] {background:white; border:1px solid #E5E7EB; border-radius:18px; padding:.75rem; box-shadow:0 1px 2px rgba(16,24,40,.05)}
[data-testid="stDataFrame"] {border-radius:16px; overflow:hidden; border:1px solid #E5E7EB; background:white;}
.filter-label {font-size:.7rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; color:#94A3B8; margin-top:1rem; margin-bottom:.35rem;}


/* =========================================================
FORCE ALL TEXT TO BLACK
========================================================= */
html, body, [class*="css"], .stApp, .stApp *,
p, span, div, label, h1, h2, h3, h4, h5, h6,
[data-testid="stSidebar"] *,
[data-testid="metric-container"] *,
[data-testid="stDataFrame"] *,
button, input, textarea, select {
    color: #000000 !important;
}

/* Keep cards and sections readable */
.hero, .hero *, .pill {
    color: #000000 !important;
}
.hero {
    background: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    box-shadow: 0 8px 24px rgba(15,23,42,.10) !important;
}
.pill {
    background: #F1F5F9 !important;
    border: 1px solid #CBD5E1 !important;
}
.section-caption, .kpi-note, .insight-text, .filter-label {
    color: #000000 !important;
}

/* Plotly SVG text */
.js-plotly-plot .plotly text,
.js-plotly-plot .plotly .gtitle,
.js-plotly-plot .plotly .xtick text,
.js-plotly-plot .plotly .ytick text,
.js-plotly-plot .plotly .legendtext {
    fill: #000000 !important;
    color: #000000 !important;
}

</style>
""", unsafe_allow_html=True)

DATA_CANDIDATES = [
    Path("cleaned/cleaned_all_jobs_deep.csv"),
    Path("/mnt/data/cleaned/cleaned_all_jobs_deep.csv"),
]

CATEGORY_PATTERNS = {
    "IT & Data": r"python|java|javascript|react|angular|php|node|sql|data|software|developer|développeur|devops|cloud|cyber|bi|power bi|machine learning|ai|web|full stack|backend|frontend|informatique",
    "Sales & Marketing": r"commercial|vente|sales|marketing|communication|crm|business development|account manager|brand|digital marketing|seo",
    "Finance & Accounting": r"finance|comptable|accounting|audit|fiscal|banque|bank|trésor|controller|contrôle de gestion",
    "Engineering & Industrial": r"ingénieur|engineer|maintenance|production|qualité|quality|industrial|mécanique|electrique|électrique|hse|technicien",
    "HR & Administration": r"ressources humaines|recrutement|rh|hr|talent|paie|assistant|administratif|secrétaire|office",
    "Logistics & Supply": r"logistique|supply chain|achat|procurement|transport|stock|warehouse|magasin",
    "Healthcare": r"santé|medical|médecin|pharmacien|infirmier|clinique",
    "Education & Training": r"enseignant|professeur|formateur|teacher|training|pédago",
}

TECH_SKILLS = {
    "python", "java", "javascript", "js", "react", "angular", "node.js", "php", "sql", "mysql", "postgresql",
    "power bi", "excel", "tableau", "machine learning", "deep learning", "ai", "docker", "linux", "cloud", "aws", "azure",
    "erp", "sap", "c#", ".net", "html", "css", "figma", "seo", "crm", "cybersecurity", "data science"
}

SOFT_SKILLS = {"communication", "management", "leadership", "teamwork", "project management", "negotiation", "problem solving"}


def clean_text(x):
    if pd.isna(x):
        return ""
    x = str(x)
    x = re.sub(r"<.*?>", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return "" if x.lower() in {"nan", "none", "null"} else x


def split_items(x):
    if pd.isna(x) or str(x).strip() == "":
        return []
    s = str(x).strip()
    try:
        value = ast.literal_eval(s)
        if isinstance(value, list):
            items = value
        else:
            items = re.split(r"[,;|/]", s)
    except Exception:
        items = re.split(r"[,;|/]", s)
    cleaned = []
    for item in items:
        item = clean_text(item).lower()
        if item and item not in {"nan", "none", "unknown"}:
            cleaned.append(item)
    return sorted(set(cleaned))


def normalize_location(x):
    x = clean_text(x)
    if not x:
        return "Unknown"
    if "," in x:
        x = x.split(",")[-1]
    return x.strip().title()


def infer_category(row):
    text = f"{row.get('title','')} {row.get('description','')} {row.get('requirements','')} {row.get('skills_text','')}".lower()
    for cat, pattern in CATEGORY_PATTERNS.items():
        if re.search(pattern, text, flags=re.I):
            return cat
    return "Other"


def experience_bucket(x):
    if pd.isna(x):
        return "Not specified"
    try:
        x = float(x)
    except Exception:
        return "Not specified"
    if x <= 1:
        return "0-1 years"
    if x <= 3:
        return "2-3 years"
    if x <= 5:
        return "4-5 years"
    return "6+ years"


def plot_layout(fig, height=390, legend=False):
    fig.update_layout(
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12, color="#000000"),
        margin=dict(l=12, r=16, t=58, b=24),
        showlegend=legend,
        title=dict(font=dict(size=15, color="#000000", family="Inter, sans-serif"), x=0.02),
    )
    fig.update_xaxes(gridcolor="#EEF2F7", zeroline=False, title_font=dict(size=12, color="#000000"), tickfont=dict(color="#000000"))
    fig.update_yaxes(gridcolor="#EEF2F7", zeroline=False, title_font=dict(size=12, color="#000000"), tickfont=dict(color="#000000"))
    return fig


@st.cache_data(show_spinner=False)
def load_data():
    data_path = next((p for p in DATA_CANDIDATES if p.exists()), None)
    if data_path is None:
        st.error("Missing cleaned dataset. Put cleaned_all_jobs_deep.csv inside the cleaned/ folder.")
        st.stop()

    df = pd.read_csv(data_path)
    df.columns = df.columns.str.strip().str.lower()

    required = ["title", "company", "location", "date", "source", "link", "description", "requirements", "responsibilities", "skills_text", "languages_text", "experience_years", "contract_type", "seniority_level"]
    for col in required:
        if col not in df.columns:
            df[col] = ""

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(clean_text)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["company"] = df["company"].replace("", "Unknown")
    df["location"] = df["location"].apply(normalize_location)
    df["skills_list"] = df["skills_text"].apply(split_items)
    df["languages_list"] = df["languages_text"].apply(split_items)
    df["num_skills"] = df["skills_list"].apply(len)
    df["num_languages"] = df["languages_list"].apply(len)
    df["experience_years"] = pd.to_numeric(df["experience_years"], errors="coerce")
    df.loc[(df["experience_years"] < 0) | (df["experience_years"] > 15), "experience_years"] = pd.NA
    df["experience_bucket"] = df["experience_years"].apply(experience_bucket)
    df["category"] = df.apply(infer_category, axis=1)
    df["seniority_level"] = df["seniority_level"].replace("", "Unknown")
    df["contract_type"] = df["contract_type"].replace("", "Unknown")
    df["has_requirements"] = df["requirements"].str.len() > 25
    df["has_responsibilities"] = df["responsibilities"].str.len() > 25
    df["deep_coverage_score"] = (
        df["has_requirements"].astype(int) +
        df["has_responsibilities"].astype(int) +
        (df["num_skills"] > 0).astype(int) +
        df["experience_years"].notna().astype(int) +
        (df["num_languages"] > 0).astype(int)
    )
    df["hard_to_fill_proxy"] = (
        (df["num_skills"] >= 4) |
        (df["experience_years"].fillna(0) >= 4) |
        (df["seniority_level"].str.contains("Senior", case=False, na=False))
    )
    df["junior_friendly"] = (
        df["seniority_level"].str.contains("Junior|Unknown", case=False, na=False) &
        (df["experience_years"].fillna(0) <= 2)
    )
    df = df.drop_duplicates(subset=["title", "company", "location", "source"])
    return df


df = load_data()

# Sidebar
with st.sidebar:
    st.markdown('<div style="font-size:1.1rem;font-weight:800;color:#0F172A;">Recruiter Filters</div>', unsafe_allow_html=True)
    st.caption("Focus the market view by source, job family, city, skill, seniority, and hiring signal.")

    st.markdown('<div class="filter-label">Market Scope</div>', unsafe_allow_html=True)
    source = st.selectbox("Source", ["All"] + sorted(df["source"].dropna().unique().tolist()))
    category = st.selectbox("Job family", ["All"] + sorted(df["category"].dropna().unique().tolist()))
    location = st.selectbox("Location", ["All"] + sorted(df["location"].dropna().unique().tolist()))
    seniority = st.selectbox("Seniority", ["All"] + sorted(df["seniority_level"].dropna().unique().tolist()))

    all_skills = sorted({skill for skills in df["skills_list"] for skill in skills})
    skill = st.selectbox("Required skill", ["All"] + all_skills)

    st.markdown('<div class="filter-label">Search</div>', unsafe_allow_html=True)
    search = st.text_input("Search title / company / description", placeholder="data analyst, react, sales...")

    st.markdown('<div class="filter-label">Recruitment Signal</div>', unsafe_allow_html=True)
    signal = st.radio("Role type", ["All roles", "Hard-to-fill proxy", "Junior-friendly"], horizontal=False)

filtered = df.copy()
if source != "All":
    filtered = filtered[filtered["source"] == source]
if category != "All":
    filtered = filtered[filtered["category"] == category]
if location != "All":
    filtered = filtered[filtered["location"] == location]
if seniority != "All":
    filtered = filtered[filtered["seniority_level"] == seniority]
if skill != "All":
    filtered = filtered[filtered["skills_list"].apply(lambda xs: skill in xs)]
if search:
    mask = (
        filtered["title"].str.contains(search, case=False, na=False) |
        filtered["company"].str.contains(search, case=False, na=False) |
        filtered["description"].str.contains(search, case=False, na=False) |
        filtered["requirements"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]
if signal == "Hard-to-fill proxy":
    filtered = filtered[filtered["hard_to_fill_proxy"]]
elif signal == "Junior-friendly":
    filtered = filtered[filtered["junior_friendly"]]

# Derived tables
skill_rows = []
for _, row in filtered.iterrows():
    for s in row["skills_list"]:
        skill_rows.append({"skill": s, "category": row["category"], "company": row["company"], "location": row["location"], "source": row["source"], "title": row["title"]})
skills_df = pd.DataFrame(skill_rows)

lang_rows = []
for _, row in filtered.iterrows():
    for lang in row["languages_list"]:
        lang_rows.append({"language": lang.title(), "category": row["category"], "title": row["title"]})
langs_df = pd.DataFrame(lang_rows)

# KPIs
jobs = len(filtered)
companies = filtered["company"].replace("Unknown", pd.NA).dropna().nunique() if jobs else 0
top_skill = skills_df["skill"].value_counts().idxmax() if not skills_df.empty else "—"
top_skill_share = (skills_df["skill"].value_counts().iloc[0] / jobs * 100) if jobs and not skills_df.empty else 0
avg_skill_intensity = filtered["num_skills"].mean() if jobs else 0
hard_share = filtered["hard_to_fill_proxy"].mean() * 100 if jobs else 0
junior_share = filtered["junior_friendly"].mean() * 100 if jobs else 0
avg_exp = filtered["experience_years"].dropna().mean() if filtered["experience_years"].notna().any() else None
coverage = (filtered["deep_coverage_score"].mean() / 5 * 100) if jobs else 0
top_company = filtered["company"].replace("Unknown", pd.NA).dropna().value_counts().idxmax() if companies else "—"
english_share = filtered["languages_list"].apply(lambda xs: "english" in [x.lower() for x in xs]).mean() * 100 if jobs else 0

st.markdown(f"""
<div class="hero">
    <h1>HR Talent Intelligence Dashboard</h1>
    <p>This dashboard transforms scraped job descriptions into recruiter-ready intelligence: skill demand, hiring difficulty, junior accessibility, language expectations, and sourcing priorities.</p>
    <span class="pill">{jobs:,} roles analyzed</span>
    <span class="pill">{companies:,} hiring companies</span>
    <span class="pill">Top skill: {top_skill}</span>
    <span class="pill">Hard-to-fill proxy: {hard_share:.0f}%</span>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-title">Recruiter Impact KPIs</div>', unsafe_allow_html=True)
st.markdown('<div class="section-caption">KPIs are designed for HR teams: sourcing priorities, skill pressure, hiring difficulty, and candidate targeting.</div>', unsafe_allow_html=True)

kpi_cols = st.columns(4)
with kpi_cols[0]:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Hiring Demand</div><div class="kpi-value">{jobs:,}</div><div class="kpi-note">Open roles matching current filters</div></div>', unsafe_allow_html=True)
with kpi_cols[1]:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Hiring Market Breadth</div><div class="kpi-value">{companies:,}</div><div class="kpi-note">Unique companies competing for talent</div></div>', unsafe_allow_html=True)
with kpi_cols[2]:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Top Sourcing Skill</div><div class="kpi-value">{top_skill}</div><div class="kpi-note">Appears in {top_skill_share:.0f}% of filtered roles</div></div>', unsafe_allow_html=True)
with kpi_cols[3]:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Skill Intensity</div><div class="kpi-value">{avg_skill_intensity:.1f}</div><div class="kpi-note">Average extracted skills per job</div></div>', unsafe_allow_html=True)

kpi_cols2 = st.columns(4)
with kpi_cols2[0]:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Hard-to-Fill Signal</div><div class="kpi-value">{hard_share:.0f}%</div><div class="kpi-note">Senior, high-experience, or multi-skill roles</div></div>', unsafe_allow_html=True)
with kpi_cols2[1]:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Junior Talent Window</div><div class="kpi-value">{junior_share:.0f}%</div><div class="kpi-note">Roles likely accessible to junior profiles</div></div>', unsafe_allow_html=True)
with kpi_cols2[2]:
    exp_value = f"{avg_exp:.1f}y" if avg_exp is not None else "—"
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Experience Pressure</div><div class="kpi-value">{exp_value}</div><div class="kpi-note">Average years required when specified</div></div>', unsafe_allow_html=True)
with kpi_cols2[3]:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">English Demand</div><div class="kpi-value">{english_share:.0f}%</div><div class="kpi-note">Roles mentioning English among languages</div></div>', unsafe_allow_html=True)

# Insight cards
st.markdown('<div class="section-title">Recruiter Decision Insights</div>', unsafe_allow_html=True)
insight_cols = st.columns(3)
with insight_cols[0]:
    st.markdown(f'<div class="insight-card"><div class="insight-title">Sourcing Priority</div><div class="insight-text">Start candidate search around <b>{top_skill}</b>, then use related co-occurring skills to refine shortlists.</div></div>', unsafe_allow_html=True)
with insight_cols[1]:
    st.markdown(f'<div class="insight-card"><div class="insight-title">Hiring Difficulty</div><div class="insight-text"><b>{hard_share:.0f}%</b> of roles show a hard-to-fill signal. Recruiters should widen sourcing channels or relax secondary requirements.</div></div>', unsafe_allow_html=True)
with insight_cols[2]:
    st.markdown(f'<div class="insight-card"><div class="insight-title">Market Competition</div><div class="insight-text">The most active employer is <b>{top_company}</b>. This helps benchmark competitor demand and talent competition.</div></div>', unsafe_allow_html=True)

# Charts
st.markdown('<div class="section-title">Talent Demand and Skill Pressure</div>', unsafe_allow_html=True)
col1, col2 = st.columns([1.15, 1], gap="large")

with col1:
    cat_counts = filtered["category"].value_counts().reset_index()
    cat_counts.columns = ["category", "roles"]
    fig = px.bar(cat_counts.sort_values("roles"), x="roles", y="category", orientation="h", text="roles", title="Hiring demand by job family")
    fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(plot_layout(fig, 420), use_container_width=True, config={"displayModeBar": False})

with col2:
    if not skills_df.empty:
        top_skills = skills_df["skill"].value_counts().head(15).reset_index()
        top_skills.columns = ["skill", "mentions"]
        fig = px.bar(top_skills.sort_values("mentions"), x="mentions", y="skill", orientation="h", text="mentions", title="Top skills recruiters should source for")
        fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(plot_layout(fig, 420), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No skills extracted for current filters.")

st.markdown('<div class="section-title">Recruitment Difficulty Signals</div>', unsafe_allow_html=True)
col3, col4, col5 = st.columns(3, gap="large")
with col3:
    exp_counts = filtered["experience_bucket"].value_counts().reindex(["Not specified", "0-1 years", "2-3 years", "4-5 years", "6+ years"]).dropna().reset_index()
    exp_counts.columns = ["experience", "roles"]
    fig = px.bar(exp_counts, x="experience", y="roles", text="roles", title="Experience pressure")
    fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
    st.plotly_chart(plot_layout(fig, 360), use_container_width=True, config={"displayModeBar": False})
with col4:
    senior_counts = filtered["seniority_level"].value_counts().reset_index()
    senior_counts.columns = ["seniority", "roles"]
    fig = px.pie(senior_counts, names="seniority", values="roles", hole=.55, title="Seniority mix")
    st.plotly_chart(plot_layout(fig, 360, legend=True), use_container_width=True, config={"displayModeBar": False})
with col5:
    if not langs_df.empty:
        lang_counts = langs_df["language"].value_counts().reset_index()
        lang_counts.columns = ["language", "mentions"]
        fig = px.bar(lang_counts, x="language", y="mentions", text="mentions", title="Language demand")
        fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
        st.plotly_chart(plot_layout(fig, 360), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No language data for current filters.")

st.markdown('<div class="section-title">Skill Granularity Matrix</div>', unsafe_allow_html=True)
st.markdown('<div class="section-caption">Shows which job families demand which skills, useful for recruiter sourcing strategy and candidate screening.</div>', unsafe_allow_html=True)
if not skills_df.empty:
    top_matrix_skills = skills_df["skill"].value_counts().head(12).index
    matrix = skills_df[skills_df["skill"].isin(top_matrix_skills)].groupby(["category", "skill"]).size().reset_index(name="mentions")
    fig = px.density_heatmap(matrix, x="skill", y="category", z="mentions", histfunc="sum", title="Skill demand by job family")
    fig.update_xaxes(tickangle=35)
    st.plotly_chart(plot_layout(fig, 430), use_container_width=True, config={"displayModeBar": False})
else:
    st.info("No skill matrix available for current filters.")

st.markdown('<div class="section-title">Skill Co-occurrence for Screening</div>', unsafe_allow_html=True)
if jobs:
    pairs = {}
    for skills in filtered["skills_list"]:
        for a, b in combinations(sorted(set(skills))[:12], 2):
            pairs[(a, b)] = pairs.get((a, b), 0) + 1
    pair_df = pd.DataFrame([{"skill_pair": f"{a} + {b}", "mentions": v} for (a, b), v in pairs.items()]).sort_values("mentions", ascending=False).head(12)
    if not pair_df.empty:
        fig = px.bar(pair_df.sort_values("mentions"), x="mentions", y="skill_pair", orientation="h", text="mentions", title="Most common skill combinations")
        fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(plot_layout(fig, 420), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Not enough skill pairs for current filters.")

st.markdown('<div class="section-title">Company Intelligence</div>', unsafe_allow_html=True)
col6, col7 = st.columns([1, 1], gap="large")
with col6:
    company_counts = filtered[filtered["company"] != "Unknown"]["company"].value_counts().head(12).reset_index()
    company_counts.columns = ["company", "roles"]
    if not company_counts.empty:
        fig = px.bar(company_counts.sort_values("roles"), x="roles", y="company", orientation="h", text="roles", title="Most active hiring companies")
        fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(plot_layout(fig, 410), use_container_width=True, config={"displayModeBar": False})
with col7:
    loc_counts = filtered["location"].value_counts().head(12).reset_index()
    loc_counts.columns = ["location", "roles"]
    fig = px.bar(loc_counts.sort_values("roles"), x="roles", y="location", orientation="h", text="roles", title="Recruitment hotspots by location")
    fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(plot_layout(fig, 410), use_container_width=True, config={"displayModeBar": False})


st.markdown('<div class="section-title">Recruiter Added-Value Analytics</div>', unsafe_allow_html=True)
st.markdown('<div class="section-caption">Extra views designed for HR teams: role complexity, source quality, language requirements, and junior hiring opportunities.</div>', unsafe_allow_html=True)

col8, col9 = st.columns([1, 1], gap="large")
with col8:
    complexity_df = filtered.copy()
    if not complexity_df.empty:
        complexity_df["complexity"] = pd.cut(
            complexity_df["num_skills"],
            bins=[-1, 0, 2, 4, 100],
            labels=["No skills listed", "Low", "Medium", "High"]
        )
        comp_counts = complexity_df["complexity"].value_counts().reindex(["No skills listed", "Low", "Medium", "High"]).dropna().reset_index()
        comp_counts.columns = ["complexity", "roles"]
        fig = px.bar(comp_counts, x="complexity", y="roles", text="roles", title="Role complexity by number of required skills")
        fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
        st.plotly_chart(plot_layout(fig, 380), use_container_width=True, config={"displayModeBar": False})

with col9:
    source_quality = filtered.groupby("source").agg(
        roles=("title", "count"),
        avg_skills=("num_skills", "mean"),
        avg_coverage=("deep_coverage_score", "mean"),
        hard_to_fill=("hard_to_fill_proxy", "mean")
    ).reset_index()
    if not source_quality.empty:
        source_quality["hard_to_fill"] = source_quality["hard_to_fill"] * 100
        fig = px.scatter(
            source_quality,
            x="avg_skills",
            y="hard_to_fill",
            size="roles",
            color="source",
            text="source",
            title="Source quality: skill depth vs hard-to-fill roles",
            labels={"avg_skills": "Avg skills per role", "hard_to_fill": "Hard-to-fill roles (%)"}
        )
        fig.update_traces(textposition="top center")
        st.plotly_chart(plot_layout(fig, 380, legend=True), use_container_width=True, config={"displayModeBar": False})

col10, col11 = st.columns([1, 1], gap="large")
with col10:
    if not skills_df.empty:
        tech_soft_rows = []
        for s in skills_df["skill"]:
            kind = "Technical" if s in TECH_SKILLS else "Soft" if s in SOFT_SKILLS else "Business / Other"
            tech_soft_rows.append(kind)
        skill_type_df = pd.DataFrame({"skill_type": tech_soft_rows})
        skill_type_counts = skill_type_df["skill_type"].value_counts().reset_index()
        skill_type_counts.columns = ["skill_type", "mentions"]
        fig = px.pie(skill_type_counts, names="skill_type", values="mentions", hole=.52, title="Skill demand profile: technical vs soft skills")
        st.plotly_chart(plot_layout(fig, 380, legend=True), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No skill type data for current filters.")

with col11:
    junior_by_cat = filtered.groupby("category").agg(
        roles=("title", "count"),
        junior_share=("junior_friendly", "mean")
    ).reset_index()
    if not junior_by_cat.empty:
        junior_by_cat["junior_share"] = junior_by_cat["junior_share"] * 100
        junior_by_cat = junior_by_cat.sort_values("junior_share", ascending=False).head(10)
        fig = px.bar(
            junior_by_cat.sort_values("junior_share"),
            x="junior_share",
            y="category",
            orientation="h",
            text=junior_by_cat["junior_share"].round(0).astype(str) + "%",
            title="Best job families for junior hiring"
        )
        fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(plot_layout(fig, 380), use_container_width=True, config={"displayModeBar": False})

st.markdown('<div class="section-title">Recruiter Benchmark Heatmap</div>', unsafe_allow_html=True)
st.markdown('<div class="section-caption">Compares hiring difficulty across job families and experience buckets.</div>', unsafe_allow_html=True)
if not filtered.empty:
    heat = filtered.groupby(["category", "experience_bucket"]).agg(
        hard_share=("hard_to_fill_proxy", "mean"),
        roles=("title", "count")
    ).reset_index()
    heat["hard_share"] = heat["hard_share"] * 100
    fig = px.density_heatmap(
        heat,
        x="experience_bucket",
        y="category",
        z="hard_share",
        histfunc="avg",
        title="Hard-to-fill intensity by job family and experience level",
        labels={"hard_share": "Hard-to-fill %", "experience_bucket": "Experience", "category": "Job family"}
    )
    st.plotly_chart(plot_layout(fig, 430), use_container_width=True, config={"displayModeBar": False})

st.markdown('<div class="section-title">Recruiter Job Explorer</div>', unsafe_allow_html=True)
st.markdown('<div class="section-caption">Use this table to inspect detailed requirements, responsibilities, skills, and links behind each role.</div>', unsafe_allow_html=True)

table_cols = ["title", "company", "location", "category", "seniority_level", "experience_years", "skills_text", "languages_text", "requirements", "responsibilities", "source", "link"]
for c in table_cols:
    if c not in filtered.columns:
        filtered[c] = ""
table = filtered[table_cols].copy()
table["experience_years"] = table["experience_years"].fillna("")
table = table.rename(columns={
    "title": "Title", "company": "Company", "location": "Location", "category": "Job Family", "seniority_level": "Seniority",
    "experience_years": "Experience", "skills_text": "Skills", "languages_text": "Languages", "requirements": "Requirements",
    "responsibilities": "Responsibilities", "source": "Source", "link": "Link"
})
st.dataframe(
    table,
    use_container_width=True,
    height=520,
    hide_index=True,
    column_config={"Link": st.column_config.LinkColumn("Link", display_text="view ↗")}
)
