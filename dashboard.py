import streamlit as st
import requests
import json
import time

# Configuration
API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Fireline Commander", page_icon="🔥", layout="wide")

# Header
st.title("🔥 Fireline: SRE Incident Commander")
st.markdown("---")

# --- SIDEBAR: Trigger New Incident ---
st.sidebar.header("🚨 Simulate Alert")
service_name = st.sidebar.selectbox("Service", ["auth-service", "payment-service", "frontend-app"])
error_msg = st.sidebar.selectbox("Error", ["High CPU Utilization", "Database Connection Timeout", "500 Internal Server Error"])

if st.sidebar.button("Trigger Incident"):
    # Construct the payload
    payload = {
        "timestamp": "2025-10-21T03:05:00Z", # Mock timestamp for consistent ID
        "service": service_name,
        "error_message": error_msg
    }

    try:
        res = requests.post(f"{API_URL}/webhook/alert", json=payload)
        if res.status_code == 200:
            st.sidebar.success("Alert Sent! Workflow started.")
        else:
            st.sidebar.error(f"Failed: {res.text}")
    except Exception as e:
        st.sidebar.error(f"Connection Error: {e}")

# --- MAIN AREA: Active Incidents ---
st.subheader("📋 Active Investigations")

# Button to refresh the list
if st.button("Refresh Status"):
    pass # Streamlit reruns the script on click, so this just triggers a reload

try:
    # Fetch list from API
    response = requests.get(f"{API_URL}/incidents")
    incidents = response.json()

    if not incidents:
        st.info("No active incidents. System healthy.")

    for inc in incidents:
        with st.container():
            # Card Header
            col1, col2 = st.columns([1, 4])
            with col1:
                st.subheader(inc['service'])
            with col2:
                st.caption(f"ID: {inc['id']}")

            # Status and Actions
            col_a, col_b, col_c = st.columns([2, 3, 2])

            with col_a:
                st.write(f"**Trigger:** {inc['error']}")

            with col_b:
                # --- NEW: Fetch and Display Live Analysis ---
                try:
                    res = requests.get(f"{API_URL}/incident/{inc['id']}/analysis")
                    analysis_text = res.json().get("analysis", "Loading...")
                    # Display the AI's findings in a nice box
                    st.info(f"**🤖 AI Investigator:**\n\n{analysis_text}")
                except:
                    st.warning("Could not fetch analysis.")

            with col_c:
                status = inc['status']
                if status == "investigating":
                    if st.button(f"✅ Approve Fix", key=f"btn_{inc['id']}"):
                        res = requests.post(f"{API_URL}/incident/{inc['id']}/approve")
                        if res.status_code == 200:
                            st.success("Approved!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed.")
                elif status == "approved":
                    st.success("🚀 Fix Executed")

        st.markdown("---")

except Exception as e:
    st.error(f"Could not connect to API Server. Is it running? ({e})")
