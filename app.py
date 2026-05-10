import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pandas as pd
import streamlit as st
from src.ingest import load_and_harmonize
from src.risk_engine import rank_risks
from src.rag_engine import generate_advisory

st.set_page_config(page_title="SIA Engine", layout="wide")
st.title("SIA — Safety Intelligence Advisory Engine")

BEATS  = "data/beats_silver_sample_data.xlsx"
AMCARE = "data/amcare_silver_sample_data.xlsx"
TIER_ICON = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}

@st.cache_data
def get_data():
    df = load_and_harmonize(BEATS, AMCARE)
    return rank_risks(df)

df = get_data()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Insiden", len(df))
c2.metric("Total Critical", (df["risk_tier"] == "CRITICAL").sum())
c3.metric("Total High", (df["risk_tier"] == "HIGH").sum())
c4.metric("Total Masih OPEN", (df["status"] == "OPEN").sum())
c5.metric("Total Golden Rules", df["golden_violated"].sum())

st.divider()

# Section 1 - Risk Heatmap
st.subheader("Risk Heatmap")

COLS_HEATMAP = [
    "risk_tier", "risk_score",
    "event_id", "source",
    "description",
    "hazard_category", "hazard_l1", "hazard_l2",
    "golden_violated",
    "status", "status_overdue",
    "location", "fleet_area",
    "konsekuensi", "kekerapan", "nilai_resiko",
    "rca_l1", "rca_l2",
    "root_cause",
    "corrective_action",
]

RENAME = {
    "risk_tier": "Tier",
    "risk_score": "Score",
    "event_id": "ID",
    "source": "Sumber",
    "description": "Deskripsi",
    "hazard_category": "Hazard Category",
    "hazard_l1": "Hazard L1",
    "hazard_l2": "Hazard L2",
    "golden_violated": "Golden Rules",
    "status": "Status",
    "status_overdue": "Overdue",
    "location": "Lokasi",
    "fleet_area": "Fleet Area",
    "konsekuensi": "Konsekuensi",
    "kekerapan": "Kekerapan",
    "nilai_resiko": "Nilai Risiko",
    "rca_l1": "RCA L1",
    "rca_l2": "RCA L2",
    "root_cause": "Akar Masalah",
    "corrective_action": "Tindakan",
}

heatmap = df[COLS_HEATMAP].copy()
heatmap["risk_tier"] = heatmap["risk_tier"].map(lambda t: f"{TIER_ICON.get(t,'')} {t}")
heatmap["golden_violated"] = heatmap["golden_violated"].map(lambda x: "⚠ YA" if x else "—")
heatmap["nilai_resiko"] = heatmap["nilai_resiko"].fillna("—")
heatmap = heatmap.rename(columns=RENAME)

# Filter sidebar — hanya Risk Tier
with st.sidebar:
    st.markdown("### Filter")
    tier_filter = st.multiselect(
        "Risk Tier",
        options=["🔴 CRITICAL","🟠 HIGH","🟡 MEDIUM","🟢 LOW"],
        default=["🔴 CRITICAL","🟠 HIGH","🟡 MEDIUM","🟢 LOW"]
    )

# Applyfilter
mask = df["risk_tier"].map(lambda t: f"{TIER_ICON.get(t,'')} {t}").isin(tier_filter)
heatmap_filtered = heatmap[mask].reset_index(drop=True)

st.caption(f"Menampilkan {len(heatmap_filtered)} dari {len(df)} insiden")
st.dataframe(
    heatmap_filtered,
    use_container_width=True,
    height=420,
    hide_index=True,
    column_config={
        "Score": st.column_config.NumberColumn(format="%.1f"),
        "Tier": st.column_config.TextColumn(width="small"),
        "Sumber": st.column_config.TextColumn(width="small"),
        "Status": st.column_config.TextColumn(width="small"),
        "Overdue": st.column_config.TextColumn(width="medium"),
        "Estimasi?": st.column_config.TextColumn(width="small"),
        "Deskripsi": st.column_config.TextColumn(width="large"),
        "Akar Masalah": st.column_config.TextColumn(width="large"),
        "Tindakan": st.column_config.TextColumn(width="large"),
        "RCA L2": st.column_config.TextColumn(width="large"),
    }
)

st.divider()

# Section 2 - Detail Insiden & Advisory SIA
st.subheader("Detail Insiden & Advisory SIA")

left, right = st.columns(2, gap="large")

with left:
    opts = df.apply(
        lambda r: f"{TIER_ICON.get(r['risk_tier'],'')} [{r['risk_score']}] "
                  f"{r['event_id']} — {str(r['description'])[:45]}",
        axis=1
    ).tolist()

    idx = st.selectbox("Pilih insiden:", range(len(opts)),
                       format_func=lambda i: opts[i])
    row = df.iloc[idx].to_dict()

    st.markdown(f"""
**ID:** `{row['event_id']}` — `{row['source']}`

**Deskripsi:** {row['description']}

**Hazard:** {row['hazard_category']} → {row['hazard_l1']} → {row['hazard_l2']}

**Lokasi:** {row['location']} | Armada: {row['fleet_area']}

**Risk Score:** `{row['risk_score']} / 100` → {TIER_ICON.get(row['risk_tier'],'')} **{row['risk_tier']}**
    """)

    # Breakdown skor 
    with st.expander("Lihat breakdown perhitungan skor"):
        breakdown = pd.DataFrame({
            "Faktor" : ["Konsekuensi", "Kekerapan", "Golden Rules",
                         "Status + Overdue", "Keyword Bahaya"],
            "Nilai" : [
                str(row['konsekuensi']),
                str(row['kekerapan']),
                "Melanggar" if row['golden_violated'] else "Tidak Melanggar",
                f"{row['status']} {row['status_overdue']}".strip(),
                "dari teks deskripsi",
            ],
            "Skor" : [
                f"{row['s_konsekuensi']:.1f}",
                f"{row['s_kekerapan']:.1f}",
                f"{row['s_golden']:.1f}",
                f"{row['s_status']:.1f}",
                f"{row['s_keyword']:.1f}",
            ],
            "Maks" : ["35.0", "25.0", "20.0", "20.0", "10.0"],
        })
        st.dataframe(breakdown, use_container_width=True, hide_index=True)
        st.caption(f"Total: **{row['risk_score']} / 100** → **{row['risk_tier']}**")

    st.markdown(f"""
**Golden Rules:** {'⚠️ MELANGGAR' if row['golden_violated'] else 'Aman'}

**Status:** {row['status']} {row.get('status_overdue', '')}

**Akar Masalah:** {row.get('root_cause', '-')}

**RCA L1:** {row.get('rca_l1', '-')}

**RCA L2:** {row.get('rca_l2', '-')}

**Tindakan Saat Ini:** {row.get('corrective_action', '-')}

**Nilai Risiko Asli:** {row.get('nilai_resiko') or '— (dihitung engine)'}
    """)

with right:
    if st.button("🤖 Tanya SIA", type="primary", use_container_width=True):
        with st.spinner("Mencari SOP relevan dan menyusun advisory..."):
            advisory = generate_advisory(row)
            st.session_state["advisory"]    = advisory
            st.session_state["advisory_id"] = row["event_id"]

    if "advisory" in st.session_state:
        st.markdown(st.session_state["advisory"])
        st.divider()
        col_a, col_b, col_c = st.columns(3)
        if col_a.button("Terima",   use_container_width=True): st.success("Dicatat.")
        if col_b.button("Sebagian", use_container_width=True): st.warning("Ditandai.")
        if col_c.button("Tolak",    use_container_width=True): st.error("Ditolak.")
    else:
        st.info("Klik 'Tanya SIA' untuk mendapat rekomendasi berbasis SOP.")
