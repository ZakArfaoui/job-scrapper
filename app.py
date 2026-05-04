import re
import pandas as pd
import plotly.express as px
import streamlit as st

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Tunisia Job Market Dashboard",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background: linear-gradient(180deg, #F8FAFC 0%, #F3F4F6 100%);
    color: #111827;
}

.block-container {
    padding-top: 1.3rem;
    padding-bottom: 2rem;
    max-width: 1450px;
}

/* Hide Streamlit branding */
#MainMenu, footer, header {
    visibility: hidden;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #E5E7EB;
}

.sidebar-title {
    font-size: 1.1rem;
    font-weight: 800;
    color: #111827;
    margin-bottom: 0.25rem;
}

.sidebar-subtitle {
    font-size: 0.8rem;
    color: #6B7280;
    line-height: 1.45;
    margin-bottom: 1.2rem;
}

.filter-label {
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #9CA3AF;
    margin-top: 1rem;
    margin-bottom: 0.4rem;
}

/* Header */
.dash-header {
    background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 55%, #2563EB 100%);
    padding: 1.5rem 1.8rem;
    border-radius: 20px;
    color: white;
    margin-bottom: 1.1rem;
    box-shadow: 0 16px 36px rgba(15, 23, 42, 0.18);
}

.header-eyebrow {
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #BFDBFE;
    margin-bottom: 0.45rem;
}

.dash-header h1 {
    font-size: 1.9rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.04em;
}

.dash-header p {
    font-size: 0.92rem;
    color: rgba(255,255,255,0.78);
    margin: 0.5rem 0 0;
    max-width: 780px;
    line-height: 1.5;
}

.header-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.9rem;
}

.meta-pill {
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.13);
    border: 1px solid rgba(255,255,255,0.18);
    font-size: 0.75rem;
    font-weight: 600;
    color: rgba(255,255,255,0.9);
}

/* KPI cards */
[data-testid="metric-container"] {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 16px;
    padding: 1rem 1.1rem;
    box-shadow: 0 1px 2px rgba(16,24,40,0.05);
    transition: 0.2s ease;
}

[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 28px rgba(16,24,40,0.08);
}

[data-testid="metric-container"] label {
    font-size: 0.7rem !important;
    font-weight: 800 !important;
    color: #6B7280 !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
}

[data-testid="metric-container"] [data-testid="metric-value"] {
    font-size: 1.65rem !important;
    font-weight: 800 !important;
    color: #111827 !important;
}

/* Sections */
.section-title {
    font-size: 1rem;
    font-weight: 800;
    color: #111827;
    margin-top: 1.5rem;
    margin-bottom: 0.2rem;
}

.section-caption {
    font-size: 0.8rem;
    color: #6B7280;
    margin-bottom: 0.8rem;
}

/* Charts */
[data-testid="stPlotlyChart"] {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 16px;
    padding: 0.7rem;
    box-shadow: 0 1px 2px rgba(16,24,40,0.05);
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid #E5E7EB;
    background: white;
}

.table-note {
    color: #6B7280;
    font-size: 0.8rem;
    margin-top: 0.6rem;
}

.empty-state {
    background: white;
    border: 1px dashed #CBD5E1;
    border-radius: 16px;
    padding: 1.2rem;
    color: #6B7280;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONSTANTS
# ============================================================

CATEGORIES = {
    "IT & Dev": r"developer|développeur|dev |angular|react|python|java|\.net|sql|data|cloud|cyber|réseau|web|devops|test|software|erp|sap|bi |digital",
    "Finance": r"financ|comptab|audit|fiscal|trésor|banking|banque|cfo|credit|comptable|contrôle de gestion",
    "Sales & Marketing": r"commercial|vente|marketing|business dev|account|client|crm|brand|communication|export|sales",
    "HR": r"ressources humaines|\bRH\b|recrutement|paie|formation|talent",
    "Logistics": r"logistique|supply chain|approvision|achat|procurement|transport|stock|magasin",
    "Engineering": r"génie|mécani|electr|maintenance|technicien|production|qualité|hse|industriel|civil",
    "Admin & Legal": r"juriste|droit|administratif|assistant|secrétaire|office manager|coordinateur",
    "Healthcare": r"médecin|infirmier|pharmacien|santé|médical|dentiste",
    "Education": r"enseignant|professeur|formateur|pédago",
}

CAT_COLORS = {
    "IT & Dev": "#2563EB",
    "Finance": "#C026D3",
    "Sales & Marketing": "#16A34A",
    "HR": "#F97316",
    "Logistics": "#B45309",
    "Engineering": "#0891B2",
    "Admin & Legal": "#7C3AED",
    "Healthcare": "#DC2626",
    "Education": "#64748B",
    "Other": "#94A3B8",
}

SOURCE_COLORS = {
    "EmploiTunisie": "#2563EB",
    "Keejob": "#16A34A",
}

REQUIRED_COLUMNS = ["title", "location", "company", "date", "source", "link"]

# ============================================================
# FUNCTIONS
# ============================================================

def normalize_location(loc):
    if pd.isna(loc) or str(loc).strip() == "":
        return "Unknown"

    loc = re.sub(r"\s{2,}", " ", str(loc)).strip()

    if "," in loc:
        loc = loc.split(",")[-1].strip()

    return loc.title()


def categorize(title):
    text = str(title).lower()

    for category, pattern in CATEGORIES.items():
        if re.search(pattern, text, re.IGNORECASE):
            return category

    return "Other"


def safe_pct(part, total):
    if total == 0:
        return "0.0% share"
    return f"{(part / total) * 100:.1f}% share"


def top_share(series):
    if len(series) == 0:
        return "0.0% share"

    counts = series.value_counts()
    return safe_pct(counts.iloc[0], counts.sum())


def clean_plotly_layout(fig, height=380, legend=False):
    fig.update_layout(
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(
            family="Inter, sans-serif",
            size=12,
            color="#374151"
        ),
        title=dict(
            font=dict(
                size=15,
                color="#111827",
                family="Inter, sans-serif"
            ),
            x=0.02
        ),
        margin=dict(l=12, r=18, t=56, b=24),
        showlegend=legend,
    )

    fig.update_xaxes(
        showline=False,
        zeroline=False,
        gridcolor="#EEF2F7",
        tickfont=dict(color="#6B7280"),
        title_font=dict(color="#6B7280", size=12),
    )

    fig.update_yaxes(
        showline=False,
        zeroline=False,
        gridcolor="#EEF2F7",
        tickfont=dict(color="#6B7280"),
        title_font=dict(color="#6B7280", size=12),
    )

    return fig


@st.cache_data(show_spinner=False)
def load_data():
    try:
        df = pd.read_csv("cleaned/cleaned_all_jobs.csv")
    except FileNotFoundError:
        try:
            df1 = pd.read_csv("cleaned/cleaned_emploitunisie_jobs.csv")
            df2 = pd.read_csv("cleaned/cleaned_keejob_jobs.csv")
            df = pd.concat([df1, df2], ignore_index=True)
        except FileNotFoundError:
            st.error(
                "No dataset found. Please place one of these files in the same folder as app.py: "
                "cleaned_all_jobs.csv, cleaned_emploitunisie_jobs.csv, cleaned_keejob_jobs.csv"
            )
            st.stop()

    df.columns = df.columns.str.strip().str.lower()

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            if col == "date":
                df[col] = pd.NaT
            elif col == "company":
                df[col] = "Unknown"
            elif col == "location":
                df[col] = "Unknown"
            elif col == "source":
                df[col] = "Unknown"
            elif col == "link":
                df[col] = ""
            else:
                st.error(f"Missing required column: {col}")
                st.stop()

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["company"] = df["company"].replace(["nan", "None", ""], "Unknown")
    df["location"] = df["location"].apply(normalize_location)
    df["category"] = df["title"].apply(categorize)

    df = df.drop_duplicates(subset=["title", "company", "location", "source"])

    return df


# ============================================================
# LOAD DATA
# ============================================================

df = load_data()

# ============================================================
# SIDEBAR FILTERS
# ============================================================

with st.sidebar:
    st.markdown('<div class="sidebar-title">Market Filters</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sidebar-subtitle">Refine the dashboard by source, category, city, keyword, and posting period.</div>',
        unsafe_allow_html=True
    )

    st.markdown('<div class="filter-label">Dataset</div>', unsafe_allow_html=True)

    sources = ["All"] + sorted(df["source"].dropna().unique().tolist())
    selected_source = st.selectbox("Source", sources)

    categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
    selected_category = st.selectbox("Category", categories)

    locations = ["All"] + sorted(df["location"].dropna().unique().tolist())
    selected_location = st.selectbox("Location", locations)

    st.markdown('<div class="filter-label">Search</div>', unsafe_allow_html=True)

    search_query = st.text_input(
        "Job title",
        placeholder="Developer, finance, manager..."
    )

    st.markdown('<div class="filter-label">Period</div>', unsafe_allow_html=True)

    min_date = df["date"].min()
    max_date = df["date"].max()

    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.date_input(
            "Date range",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date()
        )
    else:
        date_range = None

    st.markdown("---")
    st.caption("Data source: cleaned job datasets")

# ============================================================
# FILTER DATA
# ============================================================

filtered = df.copy()

if selected_source != "All":
    filtered = filtered[filtered["source"] == selected_source]

if selected_category != "All":
    filtered = filtered[filtered["category"] == selected_category]

if selected_location != "All":
    filtered = filtered[filtered["location"] == selected_location]

if search_query:
    filtered = filtered[
        filtered["title"].str.contains(search_query, case=False, na=False)
    ]

if date_range and len(date_range) == 2:
    start_date = pd.Timestamp(date_range[0])
    end_date = pd.Timestamp(date_range[1])

    with_date = filtered[filtered["date"].notna()]
    without_date = filtered[filtered["date"].isna()]

    with_date = with_date[
        (with_date["date"] >= start_date) &
        (with_date["date"] <= end_date)
    ]

    filtered = pd.concat([with_date, without_date], ignore_index=True)

# ============================================================
# KPIS
# ============================================================

total_listings = len(filtered)
n_emploi = int((filtered["source"] == "EmploiTunisie").sum()) if total_listings else 0
n_keejob = int((filtered["source"] == "Keejob").sum()) if total_listings else 0
top_location = filtered["location"].value_counts().idxmax() if total_listings else "—"
top_category = filtered["category"].value_counts().idxmax() if total_listings else "—"
unique_companies = (
    filtered["company"]
    .replace("Unknown", pd.NA)
    .dropna()
    .nunique()
    if total_listings else 0
)

# ============================================================
# HEADER
# ============================================================

st.markdown(f"""
<div class="dash-header">
    <div class="header-eyebrow">● Market Intelligence</div>
    <h1>Tunisia Job Market Dashboard</h1>
    <p>
        Professional overview of job listings from EmploiTunisie and Keejob,
        focused on demand by job category, city, source, and publication period.
    </p>
    <div class="header-meta">
        <span class="meta-pill">{total_listings:,} listings shown</span>
        <span class="meta-pill">{unique_companies:,} companies</span>
        <span class="meta-pill">Top category: {top_category}</span>
        <span class="meta-pill">Top location: {top_location}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# KPI CARDS
# ============================================================

k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    st.metric("Total listings", f"{total_listings:,}", "after filters")

with k2:
    st.metric("EmploiTunisie", f"{n_emploi:,}", safe_pct(n_emploi, total_listings))

with k3:
    st.metric("Keejob", f"{n_keejob:,}", safe_pct(n_keejob, total_listings))

with k4:
    st.metric("Top location", top_location, top_share(filtered["location"]))

with k5:
    st.metric("Top category", top_category, top_share(filtered["category"]))

# ============================================================
# CHARTS - ROW 1
# ============================================================

st.markdown('<div class="section-title">Market Overview</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-caption">Distribution of listings by category and source platform.</div>',
    unsafe_allow_html=True
)

col1, col2 = st.columns([3, 2], gap="large")

with col1:
    cat_counts = filtered["category"].value_counts().reset_index()
    cat_counts.columns = ["category", "count"]
    cat_counts = cat_counts.sort_values("count", ascending=True)

    fig_cat = px.bar(
        cat_counts,
        x="count",
        y="category",
        orientation="h",
        color="category",
        color_discrete_map=CAT_COLORS,
        text="count",
        title=f"{top_category} leads the current job demand" if total_listings else "Category demand overview",
        labels={"count": "Listings", "category": ""}
    )

    fig_cat.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>Listings: %{x:,}<extra></extra>"
    )

    clean_plotly_layout(fig_cat, height=390, legend=False)
    fig_cat.update_yaxes(showgrid=False)

    st.plotly_chart(
        fig_cat,
        use_container_width=True,
        config={"displayModeBar": False}
    )

with col2:
    source_counts = filtered["source"].value_counts().reset_index()
    source_counts.columns = ["source", "count"]

    fig_source = px.bar(
        source_counts,
        x="source",
        y="count",
        color="source",
        color_discrete_map=SOURCE_COLORS,
        text="count",
        title="Source contribution to the dataset",
        labels={"count": "Listings", "source": ""}
    )

    fig_source.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate="<b>%{x}</b><br>Listings: %{y:,}<extra></extra>"
    )

    clean_plotly_layout(fig_source, height=390, legend=False)
    fig_source.update_xaxes(showgrid=False)

    st.plotly_chart(
        fig_source,
        use_container_width=True,
        config={"displayModeBar": False}
    )

# ============================================================
# CHARTS - ROW 2
# ============================================================

st.markdown('<div class="section-title">Location and Time Signals</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-caption">Where listings are concentrated and how postings evolved over time.</div>',
    unsafe_allow_html=True
)

col3, col4 = st.columns([2, 3], gap="large")

with col3:
    loc_counts = filtered["location"].value_counts().head(12).reset_index()
    loc_counts.columns = ["location", "count"]
    loc_counts = loc_counts.sort_values("count", ascending=True)

    fig_loc = px.bar(
        loc_counts,
        x="count",
        y="location",
        orientation="h",
        text="count",
        title=f"{top_location} is the strongest hiring hub" if total_listings else "Location concentration overview",
        labels={"count": "Listings", "location": ""},
        color_discrete_sequence=["#2563EB"]
    )

    fig_loc.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>Listings: %{x:,}<extra></extra>"
    )

    clean_plotly_layout(fig_loc, height=410, legend=False)
    fig_loc.update_yaxes(showgrid=False)

    st.plotly_chart(
        fig_loc,
        use_container_width=True,
        config={"displayModeBar": False}
    )

with col4:
    date_data = filtered[filtered["date"].notna()].copy()

    if len(date_data) > 0:
        date_counts = (
            date_data
            .groupby(["date", "source"])
            .size()
            .reset_index(name="count")
        )

        date_counts["date_label"] = date_counts["date"].dt.strftime("%b %d")

        fig_date = px.bar(
            date_counts,
            x="date_label",
            y="count",
            color="source",
            color_discrete_map=SOURCE_COLORS,
            barmode="stack",
            title="Posting activity across the selected period",
            labels={"count": "Listings", "date_label": "Date", "source": "Source"}
        )

        fig_date.update_traces(
            marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>Listings: %{y:,}<extra></extra>"
        )

        clean_plotly_layout(fig_date, height=410, legend=True)

        fig_date.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="right",
                x=1,
                title=None
            )
        )

        fig_date.update_xaxes(showgrid=False)

        st.plotly_chart(
            fig_date,
            use_container_width=True,
            config={"displayModeBar": False}
        )
    else:
        st.markdown(
            '<div class="empty-state">No date data available for the current filter selection.</div>',
            unsafe_allow_html=True
        )

# ============================================================
# TABLE
# ============================================================

st.markdown('<div class="section-title">Job Listings</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-caption">Detailed records behind the dashboard.</div>',
    unsafe_allow_html=True
)

table = filtered[["title", "category", "location", "company", "date", "source", "link"]].copy()

table["date"] = table["date"].dt.strftime("%Y-%m-%d").fillna("—")
table["company"] = table["company"].replace("Unknown", "—")

table = table.rename(columns={
    "title": "Title",
    "category": "Category",
    "location": "Location",
    "company": "Company",
    "date": "Date",
    "source": "Source",
    "link": "Link"
})

st.dataframe(
    table,
    use_container_width=True,
    height=440,
    hide_index=True,
    column_config={
        "Title": st.column_config.TextColumn("Title", width="large"),
        "Category": st.column_config.TextColumn("Category", width="medium"),
        "Location": st.column_config.TextColumn("Location", width="medium"),
        "Company": st.column_config.TextColumn("Company", width="medium"),
        "Date": st.column_config.TextColumn("Date", width="small"),
        "Source": st.column_config.TextColumn("Source", width="small"),
        "Link": st.column_config.LinkColumn("Link", display_text="view ↗")
    }
)

st.markdown(
    f'<div class="table-note">Showing {len(table):,} listings after filters.</div>',
    unsafe_allow_html=True
)