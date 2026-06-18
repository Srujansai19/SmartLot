import streamlit as st
import requests
import pandas as pd
import altair as alt  # <-- IMPORT THIS
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
BACKEND_URL = "http://127.0.0.1:5000/api"

# --- !! ADMIN CREDENTIALS !! ---
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# --- PAGE SETUP ---
st.set_page_config(
    page_title="Smart Parking Dashboard",
    page_icon="🚗",
    layout="wide"
)

# --- SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.is_admin = False
if 'forecast_data' not in st.session_state:
    st.session_state.forecast_data = None
if 'historical_data' not in st.session_state:
    st.session_state.historical_data = None


# --- API FUNCTIONS (No Changes) ---
def get_slots_data():
    try:
        response = requests.get(f"{BACKEND_URL}/slots")
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.ConnectionError:
        return None

def book_slot(slot_id):
    try:
        response = requests.post(f"{BACKEND_URL}/reserve/{slot_id}")
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Backend not reachable"}

def admin_set_status(slot_id, new_status):
    try:
        response = requests.post(
            f"{BACKEND_URL}/admin/set_status/{slot_id}", 
            json={"status": new_status}
        )
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Backend not reachable"}

def get_ml_predictions():
    try:
        response = requests.get(f"{BACKEND_URL}/ml/rush_hours")
        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "message": response.json().get('error', 'Unknown error')}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Backend not reachable"}

def get_ml_forecast():
    try:
        response = requests.get(f"{BACKEND_URL}/ml/get_forecast")
        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "message": response.json().get('error', 'Unknown error')}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Backend not reachable"}

def logout():
    st.session_state.logged_in = False
    st.session_state.is_admin = False
    st.session_state.forecast_data = None
    st.session_state.historical_data = None
    st.rerun()

# --- 1. USER DASHBOARD ---
def show_user_dashboard():
    st.title("🚗 Smart Parking System")
    st.caption("Welcome! Find and book an available parking slot.")
    
    st_autorefresh(interval=3000, limit=None, key="dashboard_refresh")
    
    slots_data = get_slots_data()
    if slots_data is None:
        st.error("Error: Could not connect to the backend server. Is it running?")
        return

    cols = st.columns(4)
    
    for i, slot in enumerate(sorted(slots_data, key=lambda x: x['slot_id'])):
        slot_id = slot['slot_id']
        status = slot['status']
        
        with cols[i]:
            container = st.container(border=True, height=200)
            container.subheader(f"Slot {slot_id}")
            
            if status == "Available":
                container.success("✅ Available")
                if container.button("Book This Slot", key=f"book_{slot_id}", use_container_width=True):
                    result = book_slot(slot_id)
                    if result.get('success'):
                        st.toast(f"Booked {slot_id}!", icon="🎉")
                        st.rerun()
                    else:
                        st.error(result.get('message', 'Booking failed'))
                        
            elif status == "Reserved":
                container.info("🔵 Reserved")
                container.write("This slot is reserved. Waiting for arrival.")
                
            elif status == "Occupied":
                container.error("🔴 Occupied")
                container.write("This slot is currently parked.")

# --- 2. ADMIN PANEL (Chart Section Updated) ---
def show_admin_panel():
    with st.sidebar:
        st.title("Admin Menu")
        st.button("Logout", on_click=logout, use_container_width=True, type="primary")

    st.title("🛠️ Admin Management Panel")
    tab1, tab2 = st.tabs(["Slot Management", "Analytics & Forecasting"])

    with tab1:
        st.subheader("Real-Time Slot Management")
        st_autorefresh(interval=5000, limit=None, key="admin_refresh")
        # ... (Slot management code is unchanged) ...
        slots_data = get_slots_data()
        if slots_data is None:
            st.error("Error: Could not connect to the backend server.")
        else:
            for slot in sorted(slots_data, key=lambda x: x['slot_id']):
                st.divider()
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.subheader(f"Slot {slot['slot_id']}")
                    st.write(f"Current Status: **{slot['status']}**")
                    st.write(f"Car Sensor: **{slot['car_present']}**")
                
                with col2:
                    options = ["Available", "Reserved", "Occupied"]
                    try:
                        current_index = options.index(slot['status'])
                    except ValueError:
                        current_index = 0
                        
                    new_status = st.selectbox(
                        "Set New Status",
                        options,
                        index=current_index,
                        key=f"select_{slot['slot_id']}"
                    )
                    
                    if st.button("Update Status", key=f"update_{slot['slot_id']}", use_container_width=True):
                        result = admin_set_status(slot['slot_id'], new_status)
                        if result.get('success'):
                            st.toast(f"Slot {slot['slot_id']} updated to {new_status}", icon="✔️")
                            st.rerun()
                        else:
                            st.error(f"Failed to update: {result.get('message')}")
    
    with tab2:
        st.subheader("📈 Predictive Analytics")

        # --- Section 1: Historical Analysis ---
        st.write("#### Historical Analysis")
        if st.button("Load Historical Data"):
            with st.spinner("Analyzing past data..."):
                preds = get_ml_predictions()
                if preds.get('success'):
                    st.session_state.historical_data = preds
                else:
                    st.error(f"Could not load analysis: {preds.get('message')}")
        
        if st.session_state.historical_data:
            preds = st.session_state.historical_data
            st.info(f"Analysis is based on **{preds.get('total_logs', 0)}** parking events logged so far.")
            
            col1, col2 = st.columns(2)
            col1.metric("Busiest Day (Historical)", preds.get('busiest_day', 'N/A'))
            col2.metric("Peak Hour (Historical)", f"{preds.get('peak_hour', 'N/A')}:00")
            
            hourly_data = preds.get('hourly_activity', {})
            if hourly_data:
                chart_data = pd.DataFrame(
                    {'Hour': range(24), 'Parking Events': [hourly_data.get(str(h), 0) for h in range(24)]}
                ).set_index('Hour')
                st.bar_chart(chart_data)
        
        st.divider()

        # --- Section 2: Future Forecast ---
        st.write("#### Future Forecast")
        col1, col2 = st.columns([1,3])
        if col1.button("Generate 48-Hour Forecast"):
            with st.spinner("Training model and generating forecast... This may take a minute..."):
                forecast_result = get_ml_forecast()
                if forecast_result.get('success'):
                    st.session_state.forecast_data = forecast_result
                    st.success("Forecast generated!")
                else:
                    st.session_state.forecast_data = None
                    st.error(f"Failed to generate forecast: {forecast_result.get('message')}")
        
        if col2.button("Clear Forecast", type="secondary"):
            st.session_state.forecast_data = None
            st.rerun()

        # --- THIS IS THE NEW, FIXED CHART ---
        if st.session_state.forecast_data:
            st.write("##### Predicted Parking Demand (Next 48 Hours)")
            st.caption("This chart shows the predicted number of parking arrivals per hour.")
            
            forecast_df = pd.DataFrame(st.session_state.forecast_data.get('forecast', []))
            
            if not forecast_df.empty:
                forecast_df['ds'] = pd.to_datetime(forecast_df['ds'])
                
                # --- THIS IS THE FIX ---
                # We filter to *only* the future rows.
                # The backend returns ALL rows (past + future), so we take the last 48.
                future_forecast_only = forecast_df.tail(48).copy()
                
                # We need to rename for easier tooltips
                future_forecast_only.rename(columns={
                    'ds': 'Time',
                    'yhat': 'Prediction',
                    'yhat_lower': 'Low',
                    'yhat_upper': 'High'
                }, inplace=True)

                # Create the Altair chart
                # 1. The base chart
                base = alt.Chart(future_forecast_only).encode(
                    x=alt.X('Time', title='Date and Time')
                )

                # 2. The confidence band
                band = base.mark_area(opacity=0.3).encode(
                    y=alt.Y('Low', title='Predicted Events'),
                    y2=alt.Y2('High'),
                )

                # 3. The prediction line
                line = base.mark_line().encode(
                    y=alt.Y('Prediction'),
                    tooltip=[
                        alt.Tooltip('Time'),
                        alt.Tooltip('Prediction', format='.2f') # Format to 2 decimals
                    ]
                )

                # 4. The prediction dots
                dots = base.mark_circle(size=60).encode(
                    y=alt.Y('Prediction'),
                    tooltip=[
                        alt.Tooltip('Time'),
                        alt.Tooltip('Prediction', format='.2f')
                    ]
                )

                # Combine them and make interactive
                chart = (band + line + dots).interactive()

                st.altair_chart(chart, use_container_width=True)

            else:
                st.warning("Forecast data is empty.")

# --- 3. LOGIN PAGE ---
def show_login_page():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.container(border=True).title("Smart Parking System Login 🚗")
        login_type = st.radio("Login as:", ("User", "Admin"), horizontal=True)
        
        if login_type == "User":
            st.write("View the public parking dashboard.")
            if st.button("Enter Dashboard", use_container_width=True):
                st.session_state.logged_in = True
                st.session_state.is_admin = False
                st.rerun()
        else:
            st.write("Enter admin credentials to manage slots.")
            with st.form("admin_login"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
                
                if submitted:
                    if username == ADMIN_USER and password == ADMIN_PASS:
                        st.session_state.logged_in = True
                        st.session_state.is_admin = True
                        st.rerun()
                    else:
                        st.error("Invalid username or password")

# --- MAIN APP ROUTER ---
if not st.session_state.logged_in:
    show_login_page()
elif st.session_state.is_admin:
    show_admin_panel()
else:
    show_user_dashboard()