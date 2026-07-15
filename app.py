import streamlit as st
import pydeck as pdk
import requests
import time
import json
import pandas as pd

# ==============================================================================
# 1. CORE ARCHITECTURE CONFIG
# ==============================================================================
st.set_page_config(page_title="AAIPSI: Autonomous Agent", layout="wide", initial_sidebar_state="expanded")

# Inject advanced CSS for the terminal look
st.markdown("""
    <style>
    .big-font {font-size:20px !important; font-weight: bold; color: #00ff00;}
    .console-box {background-color: #0e1117; padding: 20px; border-radius: 8px; font-family: 'Courier New', monospace; color: #00ff00; border: 1px solid #444; height: 300px; overflow-y: scroll;}
    </style>
""", unsafe_allow_html=True)

# Hospital Geo-Coordinates for Mumbai Routing
HOSPITALS = {
    "Penetrating": {"name": "Sion Trauma Center", "coords": [72.8624, 19.0363]},
    "Neurological": {"name": "Lilavati Hospital (Neuro Unit)", "coords": [72.8285, 19.0510]},
    "Cardiac": {"name": "Holy Family (Cardiac Center)", "coords": [72.8315, 19.0550]},
    "Default": {"name": "City General Hospital", "coords": [72.8400, 19.0500]}
}

# ==============================================================================
# 2. NETWORK & ROUTING ENGINE
# ==============================================================================
def fetch_route(start, end):
    """Fetches geometry from OSRM public API."""
    url = f"http://router.project-osrm.org/route/v1/driving/{start[0]},{start[1]};{end[0]},{end[1]}?overview=full&geometries=geojson"
    try:
        res = requests.get(url, timeout=5).json()
        return res["routes"][0]["geometry"]["coordinates"]
    except:
        return []

# ==============================================================================
# 3. SIDEBAR CONFIGURATION
# ==============================================================================
with st.sidebar:
    st.title("⚙️ AAIPSI System Config")
    st.caption("Deployment: TSEC Hackathon 2026")
    mode = st.radio("Pipeline Mode:", ["Cloud GPU (Kaggle)", "Local Simulation"])
    api_url = st.text_input("Kaggle Triage API Endpoint:", "https://your-cloudflare-tunnel.trycloudflare.com/triage")
    st.markdown("---")
    st.info("System status: ACTIVE")

# ==============================================================================
# 4. DASHBOARD UI
# ==============================================================================
st.title("🚑 AAIPSI: Autonomous Medical Dispatch")
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown('<p class="big-font">1. 911 Transcript Ingestion</p>', unsafe_allow_html=True)
    scenario = st.selectbox("Select Scenario:", ["Penetrating trauma: Shot in the chest", "Cardiac arrest: Father non-responsive"])
    transcript = st.text_area("Live Audio Feed:", value=scenario, height=150)
    
    if st.button("EXECUTE AAIPSI AGENT", type="primary", use_container_width=True):
        st.session_state.dispatch_data = None
        
        # Logic Switch: Cloud vs Local
        if mode == "Cloud GPU (Kaggle)":
            try:
                resp = requests.post(api_url, json={"transcript": transcript}, timeout=10)
                st.session_state.dispatch_data = resp.json()
            except Exception as e:
                st.error(f"Network Failure: {e}")
        else:
            # Simulated Response for offline demonstration
            st.session_state.dispatch_data = {
                "trauma_type": "Penetrating",
                "dispatch_required": True,
                "recommended_equipment": ["Tourniquet", "Chest Seal"]
            }

    st.markdown("### Agent Brain Console")
    console_display = st.empty()
    if 'dispatch_data' in st.session_state and st.session_state.dispatch_data:
        console_display.markdown(f'<div class="console-box">{json.dumps(st.session_state.dispatch_data, indent=2)}</div>', unsafe_allow_html=True)

with col2:
    map_box = st.empty()
    if 'dispatch_data' in st.session_state and st.session_state.dispatch_data:
        data = st.session_state.dispatch_data
        target = HOSPITALS.get(data.get("trauma_type"), HOSPITALS["Default"])
        
        # Path simulation
        amb_pos = [72.85, 19.01]
        pat_pos = [72.82, 19.05]
        
        route = fetch_route(amb_pos, pat_pos)
        
        # Animation Loop
        for i in range(0, len(route), 2):
            layer = pdk.Layer("ScatterplotLayer", data=[{"pos": route[i]}], get_position="pos", get_fill_color=[255, 255, 255], get_radius=500)
            map_box.pydeck_chart(pdk.Deck(initial_view_state=pdk.ViewState(latitude=19.04, longitude=72.84, zoom=12), layers=[layer]))
            time.sleep(0.05)
