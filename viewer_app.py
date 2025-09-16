import json
import time
import requests
import pandas as pd
import streamlit as st
from pathlib import Path
from streamlit_folium import st_folium
import folium

API_BASE = st.secrets.get("API_BASE", "http://127.0.0.1:8000")
DATA_DIR = Path("data/graphs")

st.set_page_config(page_title="Navigator Viewer", layout="wide")
st.title("Navigator — Map Viewer")

# --- Sidebar inputs ---
campus_keys = [p.name.removesuffix(".meta.json") for p in DATA_DIR.glob("*.meta.json")]
campus_key = st.sidebar.selectbox("Campus", campus_keys, index=campus_keys.index("upenn") if "upenn" in campus_keys else 0)

avoid_stairs = st.sidebar.checkbox("Avoid stairs", True)
prefer_indoor = st.sidebar.checkbox("Prefer indoor/covered", True)
max_distance_m = st.sidebar.slider("Max distance (m)", 200, 4000, 1500, 50)
lam_stairs = st.sidebar.slider("λ_stairs", 0, 2000, 500, 10)
lam_outdoor = st.sidebar.slider("λ_outdoor", 0, 200, 50, 5)
lam_surface = st.sidebar.slider("λ_surface", 0, 50, 10, 1)

# --- Load nodes to get center & bounds quickly (no heavy viz) ---
nodes_path = DATA_DIR / f"{campus_key}.nodes.parquet"
nodes = pd.read_parquet(nodes_path)
center_lat = float(nodes["lat"].mean())
center_lon = float(nodes["lon"].mean())


col_map, col_info = st.columns([3, 2], gap="large")

# session state
for k, v in {
    "src": None,
    "dst": None,
    "last_resp": None,
    "last_error": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


with col_map:
    m = folium.Map(location=[center_lat, center_lon], zoom_start=16, tiles="cartodbpositron")

    # show existing selections
    if st.session_state.src:
        folium.Marker(st.session_state.src, tooltip="Source", icon=folium.Icon(color="green")).add_to(m)
    if st.session_state.dst:
        folium.Marker(st.session_state.dst, tooltip="Target", icon=folium.Icon(color="red")).add_to(m)

    st.caption("Click once for Source (green), click again for Target (red). Use buttons to clear/reset.")
    folium.LatLngPopup().add_to(m)

    out = st_folium(
        m,
        height=650,
        use_container_width=True,
        returned_objects=["last_clicked"],  # <-- capture clicks
        key="map_click_v1",                 # <-- new key to avoid stale cache
    )

    # Capture clicks
    click = out.get("last_clicked")
    if click is not None:
        lat = float(click["lat"])
        lon = float(click["lng"])
        # set source first, then target
        if st.session_state.get("src") is None:
            st.session_state["src"] = [lat, lon]
            st.toast("Source set ✅", icon="✅")
            st.rerun()  # refresh to draw marker
        elif st.session_state.get("dst") is None:
            st.session_state["dst"] = [lat, lon]
            st.toast("Target set 🎯", icon="🎯")
            st.rerun()


with col_info:
    st.subheader("Route Controls")
    c1, c2, c3 = st.columns(3)
    if c1.button("Clear Source"):
        st.session_state.src = None
    if c2.button("Clear Target"):
        st.session_state.dst = None
    if c3.button("Clear Both"):
        st.session_state.src = None; st.session_state.dst = None

    can_route = st.session_state.src and st.session_state.dst
    go = st.button("Compute Route", type="primary", disabled=not can_route)

    if go and can_route:
        payload = {
            "campus_key": campus_key,
            "source": {"lat": st.session_state.src[0], "lon": st.session_state.src[1]},
            "target": {"lat": st.session_state.dst[0], "lon": st.session_state.dst[1]},
            "prefs": {
                "avoid_stairs": avoid_stairs,
                "prefer_indoor": prefer_indoor,
                "max_distance_m": max_distance_m,
                "lambda": {"stairs": lam_stairs, "outdoor": lam_outdoor, "surface": lam_surface}
            }
        }
        st.session_state.last_resp = None
        st.session_state.last_error = None
        t0 = time.time()
        with st.spinner("Routing…"):
            try:
                r = requests.post(f"{API_BASE}/route", json=payload, timeout=20)
                # capture server message if not OK
                if not r.ok:
                    st.session_state.last_error = f"({r.status_code}) {r.text}"
                else:
                    st.session_state.last_resp = r.json()
            except Exception as e:
                st.session_state.last_error = str(e)
        st.rerun()  # persist and redraw

    # ---- Persisted output (shown on every rerun) ----
    if st.session_state.last_error:
        st.error(f"Routing failed: {st.session_state.last_error}")

    if st.session_state.last_resp:
        resp = st.session_state.last_resp
        totals = resp.get("totals", {})
        st.success("Route OK")
        cA, cB, cC = st.columns(3)
        cA.metric("Distance (m)", f"{totals.get('distance_m', 0):.0f}")
        cB.metric("Stairs edges", totals.get("stairs_edges", 0))
        cC.metric("Indoor share", f"{totals.get('indoor_share', 0.0)*100:.0f}%")

        coords = resp["route"]["coordinates"]  # [ [lon,lat], ... ]
        preview = folium.Map(location=[coords[0][1], coords[0][0]], zoom_start=17, tiles="cartodbpositron")
        folium.PolyLine([(lat, lon) for lon, lat in coords], weight=5, opacity=0.9).add_to(preview)
        folium.Marker((coords[0][1], coords[0][0]), tooltip="Start", icon=folium.Icon(color="green")).add_to(preview)
        folium.Marker((coords[-1][1], coords[-1][0]), tooltip="End", icon=folium.Icon(color="red")).add_to(preview)
        st_folium(preview, height=450, key="preview")
        with st.expander("Raw response"):
            st.json(resp)

