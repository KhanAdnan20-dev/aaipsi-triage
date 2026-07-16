import streamlit as st
import pydeck as pdk
import requests
import time
import json
import math
from streamlit_js_eval import get_geolocation

st.set_page_config(page_title="AAIPSI: Autonomous Agent", layout="wide")

if "caller_coords" not in st.session_state:
    st.session_state.caller_coords = None
if "request_caller_gps" not in st.session_state:
    st.session_state.request_caller_gps = False

st.markdown("""
    <style>
    .big-font {font-size:22px !important; font-weight: bold; color: #ff4b4b;}
    .console-box {background-color: #0e1117; padding: 15px; border-radius: 5px; font-family: monospace; color: #00ff00; border: 1px solid #333;}
    </style>
""", unsafe_allow_html=True)

HOSPITALS = {
    "Neurological": {"name": "Lilavati Hospital (Neuro Unit)", "coords": [72.8285, 19.0510], "beds": 6, "load": 0.42, "specialties": {"Neurological", "Default"}},
    "Cardiac": {"name": "Holy Family (Cardiac Center)", "coords": [72.8315, 19.0550], "beds": 4, "load": 0.56, "specialties": {"Cardiac", "Default"}},
    "Penetrating": {"name": "Sion Trauma Center", "coords": [72.8624, 19.0363], "beds": 9, "load": 0.34, "specialties": {"Penetrating", "Default"}},
    "Default": {"name": "City General Hospital", "coords": [72.8400, 19.0500], "beds": 12, "load": 0.28, "specialties": {"Neurological", "Cardiac", "Penetrating", "Default"}}
}

AMBULANCE_FLEET = [
    {"unit_id": "ALS-21", "coords": [72.8561, 19.0176], "available": True, "level": "Advanced Life Support"},
    {"unit_id": "BLS-14", "coords": [72.8445, 19.0320], "available": True, "level": "Basic Life Support"},
    {"unit_id": "ALS-08", "coords": [72.8730, 19.0425], "available": True, "level": "Advanced Life Support"},
]

def distance_km(origin, destination):
    lon1, lat1, lon2, lat2 = map(math.radians, [origin[0], origin[1], destination[0], destination[1]])
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))

def get_live_route(start, end):
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{start[0]},{start[1]};{end[0]},{end[1]}?overview=full&geometries=geojson"
    )
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        route = response.json()["routes"][0]
        return {
            "coordinates": route["geometry"]["coordinates"],
            "distance_m": route["distance"],
            "duration_s": route["duration"],
        }
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None

def match_resources(trauma_type, patient_coords):
    trauma_type = trauma_type if trauma_type in HOSPITALS else "Default"
    available_units = [unit for unit in AMBULANCE_FLEET if unit["available"]]
    if not available_units:
        return None, None, trauma_type

    eligible_units = [unit for unit in available_units if unit["level"] == "Advanced Life Support"] or available_units
    ambulance = min(eligible_units, key=lambda unit: distance_km(unit["coords"], patient_coords))

    candidates = [hospital for hospital in HOSPITALS.values() if hospital["beds"] > 0 and trauma_type in hospital["specialties"]]
    if not candidates:
        candidates = [hospital for hospital in HOSPITALS.values() if hospital["beds"] > 0]
    live_candidates = []
    for hospital in candidates:
        route = get_live_route(patient_coords, hospital["coords"])
        if route:
            live_candidates.append((hospital, route))

    if live_candidates:
        hospital, transfer_route = min(live_candidates, key=lambda item: (item[1]["distance_m"], item[0]["load"]))
    else:
        hospital = min(candidates, key=lambda item: distance_km(patient_coords, item["coords"]))
        transfer_route = None
    return ambulance, hospital, trauma_type, transfer_route

# ==============================================================================
# SIDEBAR CONFIGURATION
# ==============================================================================
with st.sidebar:
    st.title("Cloud Configuration")
    db_url = st.text_input("Firebase Database URL:", value="https://hackproj-58daf-default-rtdb.firebaseio.com/")
    st.markdown("---")
    st.markdown("**Status:** 🟢 Connected to Database Middleware")
    st.markdown("---")
    st.subheader("Caller location")
    if st.button("📍 Use caller's device GPS", use_container_width=True):
        st.session_state.request_caller_gps = True

    if st.session_state.request_caller_gps:
        gps = get_geolocation(component_key="caller_device_gps")
        if gps and gps.get("coords"):
            coords = gps["coords"]
            st.session_state.caller_coords = [coords["longitude"], coords["latitude"]]
            st.session_state.request_caller_gps = False
            st.success("Live caller location captured.")
        elif gps and gps.get("error"):
            st.session_state.request_caller_gps = False
            st.warning(f"GPS unavailable: {gps['error']['message']}")
        else:
            st.caption("Waiting for the browser's location permission…")

    with st.expander("Enter coordinates manually"):
        manual_lat = st.number_input("Latitude", value=19.0596, format="%.6f")
        manual_lon = st.number_input("Longitude", value=72.8295, format="%.6f")
        if st.button("Use entered location", use_container_width=True):
            st.session_state.caller_coords = [manual_lon, manual_lat]
            st.session_state.request_caller_gps = False
            st.success("Caller location updated.")

    if st.session_state.caller_coords:
        lon, lat = st.session_state.caller_coords
        st.caption(f"Active location: {lat:.5f}, {lon:.5f}")
    else:
        st.caption("Location required before autonomous dispatch.")

# ==============================================================================
# MAIN DASHBOARD
# ==============================================================================
st.title("🚑 AAIPSI: Autonomous Medical Dispatch")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown('<p class="big-font">1. Emergency Transcript Input</p>', unsafe_allow_html=True)
    user_input = st.text_area("Enter patient transcript:", height=200, placeholder="e.g. Patient is a 34-year-old male with a laceration on the forehead, bleeding heavily but conscious.")
    dispatch_btn = st.button("🚨 Dispatch Autonomous Agent", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### Agent Telemetry")
    console_placeholder = st.empty()

with col2:
    st.markdown('<p class="big-font">2. Live Autonomous Routing</p>', unsafe_allow_html=True)
    map_placeholder = st.empty()
    status_text = st.empty()

    view_state = pdk.ViewState(latitude=19.0450, longitude=72.8400, zoom=12, pitch=50)
    map_placeholder.pydeck_chart(pdk.Deck(initial_view_state=view_state, map_style="dark"))

# ==============================================================================
# FIREBASE EXECUTION PIPELINE
# ==============================================================================
if dispatch_btn:
    if not db_url.endswith("/"):
        db_url += "/"

    if not st.session_state.caller_coords:
        st.error("Capture the caller's device GPS or enter coordinates in the sidebar before dispatching.")
        st.stop()

    with col1:
        status_text.warning("📡 Dropping transcript into cloud database...")

        # 1. Write the transcript to Firebase
        submit_payload = {"transcript": user_input, "status": "REQUESTED", "response_json": ""}
        try:
            requests.put(f"{db_url}pipeline.json", json=submit_payload, timeout=10).raise_for_status()
        except requests.RequestException as e:
            st.error(f"Failed to write to database: {e}")
            st.stop()

        # 2. Poll for Kaggle to complete the job
        result = None
        with st.spinner("Waiting for Kaggle GPU to process data..."):
            for attempt in range(45):
                time.sleep(1)
                try:
                    check_res = requests.get(f"{db_url}pipeline.json", timeout=10).json()
                    if check_res and check_res.get("status") == "COMPLETED":
                        result = json.loads(check_res.get("response_json", "{}"))
                        break
                except:
                    pass

        if result:
            st.success("⚡ AI Analysis Complete!")

            with console_placeholder.container():
                st.markdown("#### 🧠 Intelligent Triage Assessment")

                m1, m2, m3 = st.columns(3)

                severity = str(result.get("severity_level", "3"))
                if severity == "1":
                    sev_color = "🔴"
                    status_word = "CRITICAL"
                elif severity == "2":
                    sev_color = "🟠"
                    status_word = "URGENT"
                else:
                    sev_color = "🟢"
                    status_word = "NON-URGENT"

                m1.metric(label=f"Status: {status_word}", value=f"{sev_color} Lvl {severity}")

                trauma_class = result.get("trauma_type", "General")
                if trauma_class == "Unknown" or trauma_class == "":
                    trauma_class = "General Consult"
                m2.metric(label="Trauma Class", value=trauma_class)

                m3.metric(label="Inference Speed", value=result.get("execution_latency", "N/A"))

                st.markdown("---")

                raw_equipment = result.get('recommended_equipment', [])
                
                if not raw_equipment or raw_equipment == ["Standard Kit"] or raw_equipment == ["Standard ALS Kit"]:
                    if severity == "1":
                        equipment_list = ["Defibrillator", "Oxygen", "Advanced Airway Kit", "IV Fluids"]
                    elif severity == "2":
                        equipment_list = ["Oxygen", "Stretcher", "Basic Trauma Kit"]
                    else:
                        equipment_list = ["Standard Vitals Kit", "Basic First Aid"]
                else:
                    equipment_list = raw_equipment

                st.markdown("**🎒 Required Dispatch Equipment:**")
                
                tags = "".join([f"<span style='background-color: #2e3138; padding: 5px 12px; border-radius: 15px; margin-right: 8px; font-size: 14px; border: 1px solid #555;'>{eq}</span>" for eq in equipment_list])
                st.markdown(tags, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

                bypass = result.get("bypass_llm", False)
                engine_used = "Deterministic Rules Engine (Layer 1)" if bypass else "Qwen-2.5-7B Neural Engine (Layer 2)"

                st.caption(f"**Audit Log:** {result.get('system_log', 'Processed successfully')} | **Routing via:** {engine_used}")
        else:
            st.error("❌ Timeout: Make sure the listener loop is running in Kaggle.")

    # ==============================================================================
    # MAP ANIMATION & DISPATCH DECISION
    # ==============================================================================
    if result:
        with col2:
            trauma = result.get("trauma_type", "Default")

            if result.get("dispatch_required"):
                pat_coords = st.session_state.caller_coords
                ambulance, target_hospital, matched_trauma, transfer_route = match_resources(trauma, pat_coords)
                if not ambulance or not target_hospital:
                    status_text.error("No suitable ambulance or hospital bed is currently available. Escalating to manual dispatch.")
                    st.stop()

                amb_coords = ambulance["coords"]
                hosp_coords = target_hospital["coords"]
                ambulance_route = get_live_route(amb_coords, pat_coords)
                route_1 = ambulance_route["coordinates"] if ambulance_route else []
                route_2 = transfer_route["coordinates"] if transfer_route else []
                
                eta_minutes = max(2, round(ambulance_route["duration_s"] / 60)) if ambulance_route else max(2, round(distance_km(amb_coords, pat_coords) / 0.45))
                
                if transfer_route:
                    hospital_distance_km = transfer_route["distance_m"] / 1000
                    hospital_eta_minutes = max(1, round(transfer_route["duration_s"] / 60))
                    route_summary = f"Caller to hospital: {hospital_distance_km:.1f} km by road · about {hospital_eta_minutes} min."
                else:
                    hospital_distance_km = None
                    hospital_eta_minutes = None
                    route_summary = "Live hospital road distance is temporarily unavailable."
                
                status_text.info(
                    f"**Autonomous resource match:** {ambulance['unit_id']} ({ambulance['level']}) assigned · "
                    f"{target_hospital['name']} selected for {matched_trauma} care · Ambulance ETA {eta_minutes} min.  \n\n"
                    f"**Live OSRM route:** {route_summary}"
                )

                dispatch_record = {
                    "status": "DISPATCHED",
                    "created_at": int(time.time()),
                    "incident": {"trauma_type": trauma, "severity": result.get("severity_level", "Unknown"), "patient_coords": pat_coords},
                    "ambulance": {"unit_id": ambulance["unit_id"], "level": ambulance["level"], "coords": amb_coords, "eta_to_caller_minutes": eta_minutes},
                    "hospital": {"name": target_hospital["name"], "coords": hosp_coords, "available_beds": target_hospital["beds"], "road_distance_km": hospital_distance_km, "road_eta_minutes": hospital_eta_minutes},
                }
                try:
                    requests.put(f"{db_url}dispatches/latest.json", json=dispatch_record, timeout=10).raise_for_status()
                except requests.RequestException as exc:
                    st.warning(f"Resource assignment created locally, but Firebase dispatch sync failed: {exc}")

                layer_pat = pdk.Layer("ScatterplotLayer", data=[{"pos": pat_coords}], get_position="pos", get_fill_color=[255, 0, 0, 255], get_radius=300)
                layer_hosp = pdk.Layer("ScatterplotLayer", data=[{"pos": hosp_coords}], get_position="pos", get_fill_color=[0, 0, 255, 255], get_radius=300)
                layer_path1 = pdk.Layer("PathLayer", data=[{"path": route_1}], get_path="path", get_color=[255, 165, 0, 200], width_scale=20)
                layer_path2 = pdk.Layer("PathLayer", data=[{"path": route_2}], get_path="path", get_color=[0, 255, 0, 200], width_scale=20)

                map_placeholder.pydeck_chart(pdk.Deck(layers=[layer_path1, layer_path2, layer_pat, layer_hosp], initial_view_state=view_state))

                status_text.warning(f"🚨 {ambulance['unit_id']} dispatched... tracking live GPS.")

                for i in range(0, len(route_1), 3): 
                    current_position = route_1[i]

                    amb_layer = pdk.Layer(
                        "ScatterplotLayer",
                        data=[{"pos": current_position}],
                        get_position="pos",
                        get_fill_color=[255, 255, 255, 255],
                        get_radius=150 
                    )

                    dynamic_view = pdk.ViewState(
                        latitude=current_position[1],
                        longitude=current_position[0],
                        zoom=15.5, 
                        pitch=65,  
                        bearing=0
                    )

                    map_placeholder.pydeck_chart(pdk.Deck(
                        layers=[layer_path1, layer_path2, layer_pat, layer_hosp, amb_layer],
                        initial_view_state=dynamic_view,
                        map_style="dark"
                    ))

                    time.sleep(0.08) 

                if route_1:
                    status_text.success(f"✅ {ambulance['unit_id']} reached the patient. Transfer route to {target_hospital['name']} is active.")
                else:
                    status_text.warning(f"⚠️ {ambulance['unit_id']} is assigned, but live road geometry is unavailable. Showing direct dispatch view.")
                
                map_placeholder.pydeck_chart(pdk.Deck(
                    layers=[layer_path1, layer_path2, layer_pat, layer_hosp],
                    initial_view_state=view_state,
                    map_style="dark"
                ))

            else:
                target_hospital = HOSPITALS.get(trauma, HOSPITALS["Default"])
                hosp_coords = target_hospital["coords"]
                layer_hosp = pdk.Layer("ScatterplotLayer", data=[{"pos": hosp_coords}], get_position="pos", get_fill_color=[0, 0, 255, 255], get_radius=500)
                map_placeholder.pydeck_chart(pdk.Deck(layers=[layer_hosp], initial_view_state=view_state))

                status_text.success("🟢 **DISPATCH HALTED:** Patient is stable. Ambulance resources conserved.")
                st.info(f"**Action Required:** Recommend patient self-transports to {target_hospital['name']} or schedule a telehealth consult.")
