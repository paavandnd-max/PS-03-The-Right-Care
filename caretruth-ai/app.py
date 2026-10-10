"""CareTruth AI — Streamlit Dashboard.

Dark navy + teal interface with four sections:
  A. Overview        — dataset stats, completeness metrics
  B. Find Care       — live search, ranked results, evidence, distances
  C. Evidence Explorer — per-facility raw evidence and contradiction viewer
  D. Coverage & Gaps — state/city coverage charts, documentation gaps

All data comes from the actual dataset — no hardcoded statistics.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.data_loader import load_dataframe, dataset_summary
from src.search_engine import search
from src.evidence_extractor import extract_evidence_from_row
from src.contradiction_detector import detect_contradictions
from src.validator import should_abstain, validate_citation_spans
from src.analytics import (
    coverage_by_state,
    coverage_by_city,
    equipment_gap_analysis,
    facility_type_breakdown,
    pin_code_summary,
)
from src.distance import PRESET_LOCATIONS, resolve_location_query
from src import config


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CareTruth AI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.metric-card {
    background: linear-gradient(135deg, #0F2040 0%, #162B50 100%);
    border: 1px solid #1E3A6E;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.5rem;
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #00C9B1;
}
.metric-label {
    font-size: 0.85rem;
    color: #8BA7C7;
    margin-top: 0.2rem;
}

.facility-card {
    background: linear-gradient(135deg, #0F2040 0%, #142038 100%);
    border: 1px solid #1E3A6E;
    border-left: 4px solid #00C9B1;
    border-radius: 10px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    transition: transform 0.2s;
}
.facility-card:hover { transform: translateX(4px); }

.verdict-verified    { color: #00C9B1; font-weight: 600; }
.verdict-advertised  { color: #F5A623; font-weight: 600; }
.verdict-unverifiable{ color: #E74C3C; font-weight: 600; }

.contradiction-flag {
    background: rgba(231, 76, 60, 0.15);
    border: 1px solid rgba(231, 76, 60, 0.4);
    border-radius: 8px;
    padding: 0.8rem;
    margin: 0.5rem 0;
}
.citation-box {
    background: rgba(0, 201, 177, 0.1);
    border: 1px solid rgba(0, 201, 177, 0.3);
    border-radius: 8px;
    padding: 0.8rem;
    margin: 0.4rem 0;
    font-family: monospace;
    font-size: 0.85rem;
}
.abstain-box {
    background: rgba(245, 166, 35, 0.15);
    border: 2px solid #F5A623;
    border-radius: 10px;
    padding: 1.2rem;
    text-align: center;
}

/* Sidebar styling */
.css-1d391kg { background-color: #0A1628; }

/* Tab styling */
button[data-baseweb="tab"] {
    font-size: 1rem;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)


# ── Data loading with error handling ─────────────────────────────────────────
@st.cache_resource(show_spinner="Loading dataset…")
def get_dataframe():
    try:
        return load_dataframe()
    except FileNotFoundError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, str(exc)


# ── Header ─────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("# 🏥")
with col_title:
    st.markdown("# CareTruth AI")
    st.markdown(
        "<p style='color:#8BA7C7;margin-top:-12px;'>Evidence-backed Healthcare Facility Intelligence · NIT Delhi Hackathon PS-03</p>",
        unsafe_allow_html=True,
    )

st.divider()

# ── Load data ──────────────────────────────────────────────────────────────────
result = get_dataframe()
if isinstance(result, tuple):
    df, err = result
else:
    df, err = result, None

if df is None:
    st.error(f"⚠️ Dataset not found. {err}")
    st.info(
        "Place the CSV at:\n"
        f"`{config.DATASET_PATH}`\n\n"
        "Run: `copy <source> data/raw/`"
    )
    st.stop()

summary = dataset_summary(df)

# ── Navigation tabs ────────────────────────────────────────────────────────────
tab_overview, tab_find, tab_explorer, tab_coverage, tab_commits = st.tabs([
    "📊 Overview",
    "🔍 Find Care",
    "🔬 Evidence Explorer",
    "🗺️ Coverage & Gaps",
    "📜 Git Commits",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB A — OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    st.subheader("Dataset at a Glance")
    st.caption("All numbers derived from the actual loaded dataset.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-value">{summary['total_records']:,}</div>
          <div class="metric-label">Total Facility Records</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-value">{summary['with_coords']:,}</div>
          <div class="metric-label">With Valid Coordinates</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-value">{summary['with_description']:,}</div>
          <div class="metric-label">With Description</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-value">{summary['with_equipment']:,}</div>
          <div class="metric-label">With Equipment Data</div>
        </div>""", unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-value">{summary['with_named_staff']:,}</div>
          <div class="metric-label">With Named Staff</div>
        </div>""", unsafe_allow_html=True)
    with c6:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-value">{summary['with_procedures']:,}</div>
          <div class="metric-label">With Procedure Data</div>
        </div>""", unsafe_allow_html=True)
    with c7:
        pct = int(summary['with_coords'] / summary['total_records'] * 100)
        st.markdown(f"""<div class="metric-card">
          <div class="metric-value">{pct}%</div>
          <div class="metric-label">Coordinate Coverage</div>
        </div>""", unsafe_allow_html=True)
    with c8:
        desc_pct = int(summary['with_description'] / summary['total_records'] * 100)
        st.markdown(f"""<div class="metric-card">
          <div class="metric-value">{desc_pct}%</div>
          <div class="metric-label">Description Coverage</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Facilities by Type")
        ft_data = pd.DataFrame(
            list(summary["by_facility_type"].items()),
            columns=["Facility Type", "Count"]
        ).sort_values("Count", ascending=True)
        fig = px.bar(
            ft_data, x="Count", y="Facility Type", orientation="h",
            color="Count",
            color_continuous_scale=[[0, "#0F2040"], [0.5, "#1E5A6E"], [1, "#00C9B1"]],
            template="plotly_dark",
        )
        fig.update_layout(
            paper_bgcolor="#0A1628", plot_bgcolor="#0A1628",
            coloraxis_showscale=False, margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Top 15 States by Facility Count")
        st_data = pd.DataFrame(
            list(summary["by_state"].items()),
            columns=["State", "Count"]
        ).sort_values("Count", ascending=True)
        fig2 = px.bar(
            st_data, x="Count", y="State", orientation="h",
            color="Count",
            color_continuous_scale=[[0, "#142038"], [0.5, "#005F73"], [1, "#00C9B1"]],
            template="plotly_dark",
        )
        fig2.update_layout(
            paper_bgcolor="#0A1628", plot_bgcolor="#0A1628",
            coloraxis_showscale=False, margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Completeness gauge
    st.subheader("Data Completeness")
    completeness_items = {
        "Description": summary["with_description"],
        "Equipment":   summary["with_equipment"],
        "Procedures":  summary["with_procedures"],
        "Named Staff": summary["with_named_staff"],
        "Coordinates": summary["with_coords"],
    }
    total = summary["total_records"]
    comp_df = pd.DataFrame([
        {"Field": k, "Present": v, "Missing": total - v}
        for k, v in completeness_items.items()
    ])
    fig3 = px.bar(
        comp_df, x="Field", y=["Present", "Missing"],
        barmode="stack", template="plotly_dark",
        color_discrete_map={"Present": "#00C9B1", "Missing": "#1E3A6E"},
    )
    fig3.update_layout(
        paper_bgcolor="#0A1628", plot_bgcolor="#0A1628",
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", y=1.05),
    )
    st.plotly_chart(fig3, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB B — FIND CARE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_find:
    st.subheader("Find Healthcare Facilities")
    st.caption("Search facilities by healthcare requirement, time of day, and location in India.")

    # Location resolution widget
    st.markdown("##### 📍 Location Picker (Type Place Name or Choose City)")
    col_loc_preset, col_loc_text = st.columns([1, 1])

    with col_loc_preset:
        loc_preset = st.selectbox(
            "Quick Select Major Indian Cities / Hackathon Probes",
            options=["-- Type Custom Place Name / City Below --"] + list(PRESET_LOCATIONS.keys()),
            index=1,
            help="Choose a pre-configured hub or practice probe location.",
        )

    # Base coordinates
    default_lat, default_lng = 26.24, 84.40
    preset_label = ""
    if loc_preset != "-- Type Custom Place Name / City Below --":
        default_lat, default_lng = PRESET_LOCATIONS[loc_preset]
        preset_label = f"Selected Preset: {loc_preset} ({default_lat:.4f}, {default_lng:.4f})"

    with col_loc_text:
        custom_place = st.text_input(
            "Or Type Any City / District / State / PIN Code",
            placeholder="e.g. Patna, Siwan, Begusarai, New Delhi, Kolkata, 841428...",
            help="Type any city or region in India. We auto-resolve coordinates using 10,000 dataset records."
        )

    # Perform instant resolution if place typed
    if custom_place.strip():
        resolved = resolve_location_query(custom_place, df)
        if resolved:
            default_lat, default_lng, r_label = resolved
            st.success(f"📍 Resolved **'{custom_place}'** → **{r_label}** · `Lat: {default_lat:.4f}, Lon: {default_lng:.4f}`")
        else:
            st.warning(f"⚠️ Could not automatically match '{custom_place}'. Using manual coordinates.")
    elif preset_label:
        st.info(f"📍 {preset_label}")

    with st.form("find_care_form"):
        col_q, col_t = st.columns([3, 1])
        with col_q:
            query_text = st.text_area(
                "Describe the healthcare need",
                value="Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.",
                height=80,
            )
        with col_t:
            time_str = st.text_input("Time (e.g. Tuesday 14:30)", value="Tuesday 14:30")

        col_lat, col_lng, col_r, col_n = st.columns(4)
        with col_lat:
            user_lat = st.number_input("Latitude", value=float(default_lat), format="%.4f")
        with col_lng:
            user_lng = st.number_input("Longitude", value=float(default_lng), format="%.4f")
        with col_r:
            radius_km = st.number_input("Radius (km)", value=100, min_value=10, max_value=500)
        with col_n:
            max_res = st.number_input("Max results", value=5, min_value=1, max_value=10)

        submitted = st.form_submit_button("🔍 Search Facilities", use_container_width=True)

    if submitted:
        with st.spinner("Searching and ranking facilities…"):
            results, desert_flags = search(
                query_text=query_text,
                user_lat=user_lat,
                user_lng=user_lng,
                time_str=time_str,
                radius_km=radius_km,
                max_results=max_res,
                df=df,
            )

        abstain, abstain_reason = should_abstain(
            results=results,
            user_lat=user_lat,
            user_lng=user_lng,
            time_str=time_str,
        )

        if abstain or not results:
            st.markdown(f"""<div class="abstain-box">
              <h3>⚠️ Cannot Confirm a Suitable Facility</h3>
              <p style="color:#E8F4FD;">{abstain_reason or 'No facilities with sufficient evidence found.'}</p>
            </div>""", unsafe_allow_html=True)
            if desert_flags:
                for flag in desert_flags:
                    st.warning(f"🏜️ Healthcare Desert Signal — PIN: {flag.get('pin','?')} · {flag.get('signal','')}")
        else:
            st.success(f"Found **{len(results)}** facility/facilities with relevant evidence.")

            for i, r in enumerate(results):
                verdict_class = {
                    "verified": "verdict-verified",
                    "advertised_only": "verdict-advertised",
                    "unverifiable": "verdict-unverifiable",
                }.get(r.verdict, "")

                verdict_icon = {"verified": "✅", "advertised_only": "⚠️", "unverifiable": "❌"}.get(r.verdict, "?")

                with st.container():
                    st.markdown(f"""<div class="facility-card">
                      <h3>#{i+1} &nbsp; {r.facility_name}</h3>
                      <p>
                        <span class="{verdict_class}">{verdict_icon} {r.verdict.replace('_',' ').title()}</span>
                        &nbsp;&nbsp;·&nbsp;&nbsp;
                        <b>Trust:</b> {r.trust_score:.2f}
                        &nbsp;&nbsp;·&nbsp;&nbsp;
                        <b>Distance:</b> {r.distance_km} km
                        &nbsp;&nbsp;·&nbsp;&nbsp;
                        <b>PIN:</b> {r.facility_pin}
                      </p>
                      <p style="color:#8BA7C7;font-size:0.9rem;">{r.why}</p>
                    </div>""", unsafe_allow_html=True)

                    with st.expander(f"Evidence & Citations for {r.facility_name}"):
                        if r.citations:
                            st.markdown("**Citations (verbatim spans from dataset):**")
                            for c in r.citations:
                                st.markdown(f"""<div class="citation-box">
                                  <b>{c.source_field}</b>: {c.span}
                                </div>""", unsafe_allow_html=True)
                        else:
                            st.info("No verbatim citations available.")

                        if r.contradiction_flags:
                            st.markdown("**Contradictions detected:**")
                            for cf in r.contradiction_flags:
                                sev_color = "🔴" if cf.severity == "critical" else "🟡"
                                st.markdown(f"""<div class="contradiction-flag">
                                  {sev_color} <b>{cf.rule_id}</b>: {cf.description}
                                  {f'<br><i>Span: {cf.conflicting_span}</i>' if cf.conflicting_span else ''}
                                </div>""", unsafe_allow_html=True)

                        if r.why_not_runner_up:
                            st.caption(f"↳ {r.why_not_runner_up}")

                        # Trust score breakdown
                        if r.scoring:
                            st.markdown("**Score breakdown:**")
                            bd = {k: v for k, v in r.scoring.score_breakdown.items() if v != 0}
                            bd_df = pd.DataFrame(list(bd.items()), columns=["Component", "Value"])
                            st.dataframe(bd_df, use_container_width=True, hide_index=True)

            if desert_flags:
                for flag in desert_flags:
                    st.warning(f"🏜️ Desert signal: PIN {flag.get('pin','?')} — {flag.get('signal','')}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB C — EVIDENCE EXPLORER
# ═══════════════════════════════════════════════════════════════════════════════
with tab_explorer:
    st.subheader("Evidence Explorer")
    st.caption("Inspect the raw evidence and contradictions for any facility record.")

    col_search, col_idx = st.columns([3, 1])
    with col_search:
        explore_name = st.text_input("Search facility by name", value="Dr. R K Thakur Hospital")
    with col_idx:
        explore_time = st.text_input("Time context", value="Tuesday 23:30")

    if explore_name:
        matches = df[df["name_norm"].str.contains(explore_name.lower(), na=False)]
        if matches.empty:
            st.warning("No facility found with that name.")
        else:
            if len(matches) > 1:
                selected_name = st.selectbox(
                    "Multiple matches — select one:",
                    matches["name"].tolist()
                )
                row = matches[matches["name"] == selected_name].iloc[0]
            else:
                row = matches.iloc[0]

            st.markdown(f"### {row['name']}")
            st.markdown(
                f"**Row ID:** {row['row_id']} &nbsp; · &nbsp; "
                f"**PIN:** {row['zip_clean']} &nbsp; · &nbsp; "
                f"**City:** {row['address_city']} &nbsp; · &nbsp; "
                f"**State:** {row['address_stateOrRegion']} &nbsp; · &nbsp; "
                f"**Type:** {row['facilityTypeId']}"
            )

            col_raw, col_ev = st.columns(2)

            with col_raw:
                st.subheader("Raw Source Fields")
                for field_name in ("description", "capability", "procedure", "equipment", "specialties"):
                    val = row.get(field_name, "")
                    if val and val.strip().lower() not in ("null", "[]", ""):
                        with st.expander(f"📋 {field_name}"):
                            st.text(val)

            with col_ev:
                st.subheader("Extracted Evidence")
                findings = extract_evidence_from_row(row)
                flags = detect_contradictions(row, findings, time_str=explore_time)

                if not findings:
                    st.info("No capability evidence extracted.")
                else:
                    for f in findings:
                        polarity_icon = {"positive": "✅", "negative": "❌", "conditional": "⚠️", "uncertain": "❓"}.get(f.polarity, "❓")
                        st.markdown(
                            f"{polarity_icon} **{f.capability}** · *{f.source_field}*"
                            + (f" · {f.constraint}" if f.constraint else "")
                        )
                        st.markdown(f"""<div class="citation-box">{f.span[:200]}</div>""", unsafe_allow_html=True)

                if flags:
                    st.subheader("⚠️ Contradictions")
                    for cf in flags:
                        sev = "🔴" if cf.severity == "critical" else "🟡"
                        st.markdown(f"""<div class="contradiction-flag">
                          {sev} <b>{cf.rule_id}</b><br>{cf.description}
                          {f'<br><i>{cf.conflicting_span[:150]}</i>' if cf.conflicting_span else ''}
                        </div>""", unsafe_allow_html=True)
                else:
                    st.success("No contradictions detected at this time.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB D — COVERAGE & GAPS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_coverage:
    st.subheader("Coverage & Gaps")
    st.caption(
        "Dataset-derived coverage indicators only. "
        "Facility absence does not prove a medical desert — "
        "under-reporting and unlisted facilities may exist."
    )

    # State-level coverage
    state_cov = coverage_by_state(df)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Facilities per State")
        fig_state = px.bar(
            state_cov.head(15), x="total_facilities", y="state", orientation="h",
            color="total_facilities",
            color_continuous_scale=[[0, "#142038"], [1, "#00C9B1"]],
            template="plotly_dark",
            labels={"total_facilities": "Facilities", "state": "State"},
        )
        fig_state.update_layout(
            paper_bgcolor="#0A1628", plot_bgcolor="#0A1628",
            coloraxis_showscale=False, margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig_state, use_container_width=True)

    with col_b:
        st.subheader("Equipment Documentation Rate by State")
        gap_df = equipment_gap_analysis(df).head(15)
        fig_gap = px.bar(
            gap_df, x="equipment_pct", y="state", orientation="h",
            color="equipment_pct",
            color_continuous_scale=[[0, "#8B0000"], [0.5, "#F5A623"], [1, "#00C9B1"]],
            template="plotly_dark",
            labels={"equipment_pct": "Equipment Coverage (%)", "state": "State"},
        )
        fig_gap.update_layout(
            paper_bgcolor="#0A1628", plot_bgcolor="#0A1628",
            coloraxis_showscale=False, margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig_gap, use_container_width=True)

    # Map view (scatter on India coordinates)
    st.subheader("Facility Map (India)")
    coord_df = df[df["has_coords"]].copy()
    sample_map = coord_df.sample(min(2000, len(coord_df)), random_state=42)
    if hasattr(px, "scatter_map"):
        fig_map = px.scatter_map(
            sample_map,
            lat="lat_f", lon="lon_f",
            hover_name="name",
            hover_data={"address_city": True, "facilityTypeId": True, "lat_f": False, "lon_f": False},
            color="facilityTypeId",
            zoom=4, center={"lat": 20.5, "lon": 79.0},
            height=500,
            template="plotly_dark",
        )
        fig_map.update_layout(
            map_style="open-street-map",
            paper_bgcolor="#0A1628",
            margin=dict(l=0, r=0, t=0, b=0),
        )
    elif hasattr(px, "scatter_mapbox"):
        fig_map = px.scatter_mapbox(
            sample_map,
            lat="lat_f", lon="lon_f",
            hover_name="name",
            hover_data={"address_city": True, "facilityTypeId": True, "lat_f": False, "lon_f": False},
            color="facilityTypeId",
            zoom=4, center={"lat": 20.5, "lon": 79.0},
            height=500,
            template="plotly_dark",
        )
        fig_map.update_layout(
            mapbox_style="carto-darkmatter",
            paper_bgcolor="#0A1628",
            margin=dict(l=0, r=0, t=0, b=0),
        )
    else:
        fig_map = px.scatter_geo(
            sample_map,
            lat="lat_f", lon="lon_f",
            hover_name="name",
            hover_data={"address_city": True, "facilityTypeId": True, "lat_f": False, "lon_f": False},
            color="facilityTypeId",
            height=500,
            template="plotly_dark",
            scope="asia",
        )
        fig_map.update_layout(
            paper_bgcolor="#0A1628",
            margin=dict(l=0, r=0, t=0, b=0),
        )
    st.plotly_chart(fig_map, use_container_width=True)

    # City breakdown table
    st.subheader("Top 20 Cities by Facility Count")
    city_df = coverage_by_city(df)
    st.dataframe(city_df, use_container_width=True, hide_index=True)

    # State completeness table
    st.subheader("State Completeness Detail")
    st.dataframe(state_cov, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB E — GIT COMMITS & REAL-TIME ACTIVITY LOG
# ═══════════════════════════════════════════════════════════════════════════════
with tab_commits:
    st.subheader("📜 Real-Time Git Commit History & Feature Activity")
    st.caption("Live git commit stream tracking feature implementation for CareTruth AI.")

    import subprocess
    def fetch_git_commits(limit=25):
        try:
            res = subprocess.run(
                ["git", "log", f"-n{limit}", "--pretty=format:%h|%an|%ar|%s"],
                capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent)
            )
            if res.returncode == 0 and res.stdout:
                logs = []
                for line in res.stdout.strip().split("\n"):
                    p = line.split("|", 3)
                    if len(p) == 4:
                        logs.append({"Hash": p[0], "Author": p[1], "When": p[2], "Commit Message": p[3]})
                return pd.DataFrame(logs)
        except Exception as exc:
            st.error(f"Could not fetch git history: {exc}")
        return pd.DataFrame()

    commit_df = fetch_git_commits(25)
    if not commit_df.empty:
        col_c1, col_c2 = st.columns([1, 4])
        with col_c1:
            st.metric("Total Commits", len(commit_df))
        with col_c2:
            st.markdown(f"**Latest Commit Hash:** `{commit_df['Hash'].iloc[0]}` &nbsp;·&nbsp; **Author:** `{commit_df['Author'].iloc[0]}` &nbsp;·&nbsp; **Last Activity:** `{commit_df['When'].iloc[0]}`")

        st.divider()

        # Display interactive dataframe
        st.dataframe(
            commit_df,
            column_config={
                "Hash": st.column_config.TextColumn("Hash", width="small"),
                "Author": st.column_config.TextColumn("Author", width="small"),
                "When": st.column_config.TextColumn("Timestamp", width="small"),
                "Commit Message": st.column_config.TextColumn("Feature / Commit Description", width="large"),
            },
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Commit Feed")
        for idx, row in commit_df.iterrows():
            st.markdown(f"""<div style="background:#0F2040;border-left:4px solid #00C9B1;padding:0.8rem 1.2rem;border-radius:6px;margin-bottom:0.6rem;">
              <span style="background:#00C9B1;color:#0A1628;font-weight:bold;padding:2px 8px;border-radius:4px;font-family:monospace;">{row['Hash']}</span>
              &nbsp;&nbsp;<b style="color:#E8F4FD;font-size:1.05rem;">{row['Commit Message']}</b>
              <br/>
              <span style="color:#8BA7C7;font-size:0.85rem;">👤 {row['Author']} &nbsp;·&nbsp; 🕒 {row['When']}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No git commit history found.")
