import streamlit as st
import pydeck as pdk
import requests
import time
import json

st.set_page_config(page_title="AAIPSI: Autonomous Agent", layout="wide")

st.markdown("""
    <style>
    .big-font {font-size:22px !important; font-weight: bold; color: #ff4b4b;}
    .console-box {background-color: #0e1117; padding: 15px; border-radius: 5px; font-family: monospace; color: #00ff00; border: 1px solid #333;}
    </style>
""", unsafe_allow_html=True)

HOSPITALS = {
    "Neurological": {"name": "Lilavati Hospital (Neuro Unit)", "coords": [72.8285, 19.0510]},
    "Cardiac": {"name": "Holy Family (Cardiac Center)", "coords": [72.8315, 19.0550]},
    "Penetrating": {"name": "Sion Trauma Center", "coords": [72.8624, 19.0363]},
    "Default": {"name": "City General Hospital", "coords": [72.8400, 19.0500]}
}

def get_osrm_route(lon1, lat1, lon2, lat2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        res = requests.get(url, timeout=5).json()
        return res["routes"][0]["geometry"]["coordinates"] if res.get("code") == "Ok" else []
    except:
        return []

# ==============================================================================
# SIDEBAR CONFIGURATION
# ==============================================================================
with st.sidebar:
    st.title("Cloud Configuration")
    # I have set this to your newest Firebase project URL automatically
    db_url = st.text_input("Firebase Database URL:", value="https://hackproj-58daf-default-rtdb.firebaseio.com/")
    st.markdown("---")
    st.markdown("**Status:** 🟢 Connected to Database Middleware")

# ==============================================================================
# MAIN DASHBOARD
# ==============================================================================
st.title("🚑 AAIPSI: Autonomous Medical Dispatch")
st.markdown("---")

col1, col2 = st.columns([1.2, 2])

with col1:
    st.markdown('<p class="big-font">1. Incoming 911 Triage</p>', unsafe_allow_html=True)
    scenario = st.selectbox("Select Live Scenario:", [
        "myfatherisnotopeningb his eyese from 5 mins",
        "Help, my friend was shot in the chest!"
    ])
    user_input = st.text_area("Audio Transcript Transcription:", value=scenario, height=100)
    dispatch_btn = st.button("EXECUTE AAIPSI PROTOCOL", type="primary", use_container_width=True)
    
    st.markdown("### Agent Telemetry")
    console_placeholder = st.empty()

with col2:
    st.markdown('<p class="big-font">2. Live Autonomous Routing</p>', unsafe_allow_html=True)
    map_placeholder = st.empty()
    status_text = st.empty()
    
    view_state = pdk.ViewState(latitude=19.0450, longitude=72.8400, zoom=12, pitch=50)
    map_placeholder.pydeck_chart(pdk.Deck(initial_view_state=view_state, map_style='mapbox://styles/mapbox/dark-v11'))

# ==============================================================================
# FIREBASE EXECUTION PIPELINE
# ==============================================================================
if dispatch_btn:
    if not db_url.endswith("/"):
        db_url += "/"
        
    with col1:
        status_text.warning("📡 Dropping transcript into cloud database...")
        
        # 1. Write the transcript to Firebase
        submit_payload = {"transcript": user_input, "status": "REQUESTED", "response_json": ""}
        try:
            requests.put(f"{db_url}pipeline.json", json=submit_payload)
        except Exception as e:
            st.error(f"Failed to write to database: {e}")
            st.stop()
        
        # 2. Poll for Kaggle to complete the job
        result = None
        with st.spinner("Waiting for Kaggle GPU to process data..."):
            for attempt in range(45): 
                time.sleep(1)
                try:
                    check_res = requests.get(f"{db_url}pipeline.json").json()
                    if check_res and check_res.get("status") == "COMPLETED":
                        result = json.loads(check_res.get("response_json", "{}"))
                        break
                except:
                    pass
        
if result:
            st.success("⚡ AI Analysis Complete!")
            
            # Clear the placeholder and build a clean dashboard layout
            with console_placeholder.container():
                st.markdown("#### 🧠 Intelligent Triage Assessment")
                
                # Row 1: Key Metrics
                m1, m2, m3 = st.columns(3)
                
                severity = result.get("severity_level", "Unknown")
                # Add a visual warning for high severity
                sev_color = "🔴" if str(severity) == "1" else "🟠" 
                
                m1.metric(label="Severity Level", value=f"{sev_color} Priority {severity}")
                m2.metric(label="Trauma Class", value=result.get("trauma_type", "Unknown"))
                m3.metric(label="Inference Speed", value=result.get("execution_latency", "N/A"))
                
                st.markdown("---")
                
                # Row 2: Actionable Data
                equipment_list = result.get('recommended_equipment', ['Standard Kit'])
                st.markdown(f"**🎒 Required Dispatch Equipment:**")
                
                # Display equipment as styled tags/bullets
                eq_string = " • ".join(equipment_list)
                st.info(eq_string)
                
                # Row 3: System Accountability Log
                bypass = result.get("bypass_llm", False)
                engine_used = "Deterministic Rules Engine (Layer 1)" if bypass else "Qwen-2.5-7B Neural Engine (Layer 2)"
                
                st.caption(f"**Audit Log:** {result.get('system_log', 'Processed successfully')} | **Routing via:** {engine_used}")
        else:
            st.error("❌ Timeout: Make sure the listener loop is running in Kaggle.")

    # ==============================================================================
    # MAP ANIMATION
    # ==============================================================================
    if result and result.get("dispatch_required"):
        with col2:
            trauma = result.get("trauma_type", "Default")
            target_hospital = HOSPITALS.get(trauma, HOSPITALS["Default"])
            status_text.info(f"**Selected:** {target_hospital['name']} for {trauma} trauma.")
            
            amb_coords = [72.8561, 19.0176]
            pat_coords = [72.8295, 19.0596]
            hosp_coords = target_hospital["coords"]
            
            route_1 = get_osrm_route(amb_coords[0], amb_coords[1], pat_coords[0], pat_coords[1])
            route_2 = get_osrm_route(pat_coords[0], pat_coords[1], hosp_coords[0], hosp_coords[1])
            
            layer_pat = pdk.Layer("ScatterplotLayer", data=[{"pos": pat_coords}], get_position="pos", get_fill_color=[255, 0, 0, 255], get_radius=300)
            layer_hosp = pdk.Layer("ScatterplotLayer", data=[{"pos": hosp_coords}], get_position="pos", get_fill_color=[0, 0, 255, 255], get_radius=300)
            layer_path1 = pdk.Layer("PathLayer", data=[{"path": route_1}], get_path="path", get_color=[255, 165, 0, 200], width_scale=20)
            layer_path2 = pdk.Layer("PathLayer", data=[{"path": route_2}], get_path="path", get_color=[0, 255, 0, 200], width_scale=20)
            
            map_placeholder.pydeck_chart(pdk.Deck(layers=[layer_path1, layer_path2, layer_pat, layer_hosp], initial_view_state=view_state))
            
            status_text.warning("🚨 Ambulance Dispatched...")
            for i in range(0, len(route_1), 4):
                amb_layer = pdk.Layer("ScatterplotLayer", data=[{"pos": route_1[i]}], get_position="pos", get_fill_color=[255, 255, 255, 255], get_radius=400)
                map_placeholder.pydeck_chart(pdk.Deck(layers=[layer_path1, layer_path2, layer_pat, layer_hosp, amb_layer], initial_view_state=view_state))
                time.sleep(0.05)
            
            status_text.success(f"✅ Route to {target_hospital['name']} Active.")
