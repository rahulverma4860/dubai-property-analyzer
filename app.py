import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Dubai Property Analyzer", page_icon="🏙️", layout="wide")
st.title("🏙️ Dubai Property Market Analyzer")
st.caption("1M+ DLD historical transactions + Live Bayut market data · Powered by Python")
st.divider()

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = "uae-real-estate3.p.rapidapi.com"

# ── Load DLD historical data ───────────────────────────────────────────────────
@st.cache_data
def load_dld_data():
    if not os.path.exists("transactions.csv"):
        st.warning("📂 Running in demo mode — DLD CSV not available on cloud. Live Bayut tab is fully functional.")
        # Return sample data
        data = {
            "area": ["Dubai Marina","Downtown Dubai","JVC","Business Bay","Palm Jumeirah",
                     "JVC","Dubai Marina","Downtown Dubai","Arabian Ranches","JBR"],
            "property_type": ["Residential","Residential","Residential","Residential","Residential",
                              "Residential","Residential","Residential","Residential","Residential"],
            "property_subtype": ["Apartment","Apartment","Apartment","Apartment","Villa",
                                 "Apartment","Apartment","Penthouse","Villa","Apartment"],
            "size_sqft": [850,1200,700,950,4500,680,1100,3200,3800,900],
            "price_aed": [1_400_000,2_800_000,750_000,1_600_000,12_000_000,
                          700_000,1_850_000,9_500_000,4_200_000,1_550_000],
            "year": [2024,2024,2024,2023,2024,2023,2024,2024,2023,2024],
            "rooms": ["1 B/R","2 B/R","Studio","1 B/R","5 B/R","Studio","2 B/R","4 B/R","5 B/R","1 B/R"],
            "project": ["Marina Gate","Burj Vista","Bloom Towers","DAMAC Towers","Signature Villas",
                        "Park Lane","Marina Crown","The Address","Saheel","Bahar"],
            "nearest_metro": ["DMCC","Burj Khalifa","No Metro","Business Bay","No Metro",
                              "No Metro","DMCC","Burj Khalifa","No Metro","DMCC"],
            "parking": ["Yes","Yes","No","Yes","Yes","No","Yes","Yes","Yes","Yes"],
            "trans_type": ["Sales","Sales","Sales","Sales","Sales","Sales","Sales","Sales","Sales","Sales"],
        }
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime("2024-01-01")
        df["price_per_sqft"] = (df["price_aed"] / df["size_sqft"]).round(0)
        return df

df = load_dld_data()

# ── Bayut API helpers ──────────────────────────────────────────────────────────
def get_headers():
    return {
        "x-rapidapi-key":  RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

@st.cache_data(ttl=3600)
def autocomplete_location(query):
    """Returns list of {name, externalID} from Bayut autocomplete."""
    try:
        r = requests.get(
            f"https://{RAPIDAPI_HOST}/autocomplete",
            headers=get_headers(),
            params={"query": query},
            timeout=10
        )
        data = r.json()
        locs = data.get("data", {}).get("locations", [])
        return [{"name": l["name"]["en"], "id": l["externalID"]} for l in locs]
    except Exception:
        return []

@st.cache_data(ttl=3600)
def fetch_bayut_transactions(purpose, location_id, beds, pages=3):
    """Fetch live transactions from Bayut API."""
    all_hits = []
    for page in range(1, pages + 1):
        params = {
            "purpose":             purpose,
            "locationExternalIDs": location_id,
            "hitsPerPage":         "50",
            "page":                str(page),
        }
        if beds != "Any":
            params["beds"] = beds
        try:
            r = requests.get(
                f"https://{RAPIDAPI_HOST}/transactions",
                headers=get_headers(),
                params=params,
                timeout=10
            )
            hits = r.json().get("data", {}).get("hits", [])
            if not hits:
                break
            all_hits.extend(hits)
        except Exception:
            break

    if not all_hits:
        return pd.DataFrame()

    rows = []
    for h in all_hits:
        try:
            sqm  = float(h.get("builtup_area_sqm") or 0)
            sqft = round(sqm * 10.764, 0) if sqm else None
            price = float(h.get("transaction_amount") or 0) or None
            rows.append({
                "date":          h.get("date_transaction_nk", "")[:10],
                "area":          h.get("bayut_location_l3_name_en", "—"),
                "building":      h.get("bayut_leaf_location_name_en", "—"),
                "beds":          h.get("beds", "—"),
                "floor":         h.get("floor", "—"),
                "size_sqft":     sqft,
                "price_aed":     price,
                "price_per_sqft": round(price / sqft, 0) if price and sqft else None,
                "lat":           float(h.get("latitude") or 0) or None,
                "lng":           float(h.get("longitude") or 0) or None,
            })
        except Exception:
            continue

    ldf = pd.DataFrame(rows).dropna(subset=["price_aed", "size_sqft"])
    ldf = ldf[(ldf["price_aed"] > 50_000) & (ldf["size_sqft"] > 50)]
    return ldf

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["📊 Historical DLD Data (1M+ records)", "🔴 Live Bayut Transactions"])

# ── TAB 1: Historical DLD ──────────────────────────────────────────────────────
with tab1:
    st.success(f"✅ {len(df):,} real DLD transactions loaded")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        property_type = st.selectbox("Property Type",
            ["All"] + sorted(df["property_type"].dropna().unique().tolist()), key="t1_type")
    with col_f2:
        area = st.selectbox("Area",
            ["All"] + sorted(df["area"].dropna().unique().tolist()), key="t1_area")
    with col_f3:
        all_years  = sorted(df["year"].dropna().unique().astype(int).tolist())
        year_range = st.select_slider("Year Range", options=all_years,
                                       value=(min(all_years), max(all_years)), key="t1_year")
    with col_f4:
        p_min = int(df["price_aed"].quantile(0.01))
        p_max = int(df["price_aed"].quantile(0.99))
        min_p, max_p = st.slider("Price (AED)", p_min, p_max, (p_min, p_max),
                                  step=100_000, format="AED %d", key="t1_price")

    filt = df.copy()
    if property_type != "All": filt = filt[filt["property_type"] == property_type]
    if area          != "All": filt = filt[filt["area"] == area]
    filt = filt[(filt["year"] >= year_range[0]) & (filt["year"] <= year_range[1])]
    filt = filt[(filt["price_aed"] >= min_p) & (filt["price_aed"] <= max_p)]

    st.divider()
    if len(filt) == 0:
        st.warning("No data matches — adjust filters.")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.metric("Transactions",   f"{len(filt):,}")
        with c2: st.metric("Avg Price",      f"AED {filt['price_aed'].mean():,.0f}")
        with c3: st.metric("Avg Price/sqft", f"AED {filt['price_per_sqft'].mean():,.0f}")
        with c4: st.metric("Avg Size",       f"{filt['size_sqft'].mean():,.0f} sqft")
        with c5: st.metric("Total Volume",   f"AED {filt['price_aed'].sum()/1e9:.2f}B")

        st.divider()
        ca, cb = st.columns(2)
        with ca:
            st.subheader("Avg Price/sqft by Area (Top 15)")
            ta = (filt.groupby("area")["price_per_sqft"].mean().reset_index()
                  .sort_values("price_per_sqft", ascending=False).head(15))
            fig1 = px.bar(ta, x="price_per_sqft", y="area", orientation="h",
                          color="price_per_sqft", color_continuous_scale="Oranges",
                          labels={"price_per_sqft":"AED/sqft","area":""})
            fig1.update_layout(coloraxis_showscale=False, margin=dict(l=0,r=0,t=10,b=0),
                               yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig1, use_container_width=True)
        with cb:
            st.subheader("Volume by Year")
            yr = filt.groupby("year").agg(count=("price_aed","count"),
                                           avg=("price_aed","mean")).reset_index()
            fig2 = px.bar(yr, x="year", y="count",
                          labels={"year":"Year","count":"Transactions"},
                          color_discrete_sequence=["#E8593C"])
            fig2.update_layout(margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Avg Price Trend by Year")
        fig3 = px.line(yr, x="year", y="avg", markers=True,
                       labels={"year":"Year","avg":"Avg Price (AED)"},
                       color_discrete_sequence=["#E8593C"])
        fig3.update_layout(margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig3, use_container_width=True)

        with st.expander("📋 Raw data"):
            show = ["date","area","property_subtype","rooms","size_sqft",
                    "price_aed","price_per_sqft","project","nearest_metro","parking"]
            av = [c for c in show if c in filt.columns]
            st.dataframe(filt[av].head(500).style.format({
                "price_aed":"AED {:,.0f}","price_per_sqft":"AED {:,.0f}","size_sqft":"{:,.0f}"
            }), use_container_width=True)

# ── TAB 2: Live Bayut ──────────────────────────────────────────────────────────
with tab2:
    if not RAPIDAPI_KEY:
        st.warning("⚠️ No API key found. Add RAPIDAPI_KEY to your .env file.")
    else:
        st.success("🔴 Live transaction data pulled directly from Bayut")

        col_l1, col_l2, col_l3 = st.columns(3)
        with col_l1:
            purpose = st.selectbox("Purpose", ["for-sale", "for-rent"], key="live_purpose")
        with col_l2:
            location_query = st.text_input("Area / Community", value="Dubai Marina", key="live_loc")
        with col_l3:
            beds = st.selectbox("Bedrooms", ["Any","0","1","2","3","4","5"], key="live_beds")

        if st.button("🔍 Fetch Live Data", type="primary"):

            # Resolve location name → ID
            with st.spinner("Looking up location..."):
                locs = autocomplete_location(location_query)

            if not locs:
                st.error("Location not found. Try 'Dubai Marina', 'JVC', 'Business Bay' etc.")
            else:
                # Show location picker if multiple results
                loc_names = [l["name"] for l in locs[:5]]
                chosen    = st.selectbox("Select exact location", loc_names, key="loc_pick")
                loc_id    = next(l["id"] for l in locs if l["name"] == chosen)

                with st.spinner(f"Fetching live transactions for {chosen}..."):
                    live = fetch_bayut_transactions(purpose, loc_id, beds)

                if live.empty:
                    st.error("No transactions found. Try a different area or date range.")
                else:
                    st.success(f"Found **{len(live):,}** live transactions in **{chosen}**")

                    c1, c2, c3, c4 = st.columns(4)
                    with c1: st.metric("Transactions",   f"{len(live):,}")
                    with c2: st.metric("Avg Price",      f"AED {live['price_aed'].mean():,.0f}")
                    with c3: st.metric("Avg Price/sqft", f"AED {live['price_per_sqft'].mean():,.0f}")
                    with c4: st.metric("Avg Size",       f"{live['size_sqft'].mean():,.0f} sqft")

                    st.divider()
                    cl, cr = st.columns(2)

                    with cl:
                        st.subheader("Price Distribution")
                        fig_l1 = px.histogram(live, x="price_aed", nbins=20,
                                              color_discrete_sequence=["#E8593C"],
                                              labels={"price_aed":"Price (AED)"})
                        fig_l1.update_layout(margin=dict(l=0,r=0,t=10,b=0))
                        st.plotly_chart(fig_l1, use_container_width=True)

                    with cr:
                        st.subheader("Transactions by Bedrooms")
                        bc = live["beds"].value_counts().reset_index()
                        bc.columns = ["Bedrooms","Count"]
                        fig_l2 = px.pie(bc, names="Bedrooms", values="Count",
                                        color_discrete_sequence=px.colors.sequential.Oranges_r)
                        fig_l2.update_layout(margin=dict(l=0,r=0,t=10,b=0))
                        st.plotly_chart(fig_l2, use_container_width=True)

                    # Map if coordinates available
                    map_data = live.dropna(subset=["lat","lng"])
                    map_data = map_data[(map_data["lat"] != 0) & (map_data["lng"] != 0)]
                    if len(map_data) > 0:
                        st.subheader("Transaction Map")
                        fig_map = px.scatter_mapbox(
                            map_data, lat="lat", lon="lng",
                            color="price_aed", size="price_aed",
                            hover_data=["area","beds","size_sqft","price_per_sqft"],
                            color_continuous_scale="Oranges",
                            zoom=12, height=450,
                            mapbox_style="carto-positron",
                            labels={"price_aed":"Price (AED)"}
                        )
                        fig_map.update_layout(margin=dict(l=0,r=0,t=10,b=0))
                        st.plotly_chart(fig_map, use_container_width=True)

                    st.subheader("Live Transactions Table")
                    st.dataframe(
                        live[["date","area","building","beds","floor",
                               "size_sqft","price_aed","price_per_sqft"]]
                        .sort_values("date", ascending=False)
                        .style.format({
                            "price_aed":      "AED {:,.0f}",
                            "price_per_sqft": "AED {:,.0f}",
                            "size_sqft":      "{:,.0f}"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

st.divider()
st.caption("Stage 3 of 4 · 1M+ DLD records + Live Bayut API · Next: GitHub + deploy online · Built by [Your Name] — Real Estate Agent & Python Developer")