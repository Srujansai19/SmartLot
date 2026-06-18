import pymongo
import os  # For environment variables
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime  # For logging
import pandas as pd  # For ML
from bson import json_util  # For ML
from prophet import Prophet  # For ML Forecasting
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")

if not MONGO_URL:
    print("Error: MONGO_URL environment variable is not set.")
    print("Please set it by running: export MONGO_URL=\"your_connection_string\"")
    exit()

DB_NAME = "smart_parking"
COLLECTION_NAME = "slots"
LOG_COLLECTION_NAME = "parking_log"  # For ML data

# --- FLASK & MONGO SETUP ---
app = Flask(__name__)
CORS(app)

try:
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]  # The 'slots' collection
    log_collection = db[LOG_COLLECTION_NAME]  # The 'parking_log' collection
    print("Connected to MongoDB!")
except pymongo.errors.ConnectionFailure as e:
    print(f"Could not connect to MongoDB: {e}")
    exit()

# --- HELPER: Log status changes ---
def log_status_change(slot_id, new_status, source):
    """
    Logs a status change to our new 'parking_log' collection.
    """
    log_entry = {
        "slot_id": slot_id,
        "status": new_status,
        "timestamp": datetime.now(),
        "source": source  # e.g., "sensor", "user_booking", "admin"
    }
    try:
        log_collection.insert_one(log_entry)
    except Exception as e:
        print(f"Error logging to parking_log: {e}")


# --- HELPER SCRIPT: Create the 4 slots if they don't exist ---
def initialize_slots():
    print("Initializing slots...")
    for i in range(1, 5):
        slot_id = f"A{i}"
        if not collection.find_one({"slot_id": slot_id}):
            collection.insert_one({
                "slot_id": slot_id,
                "status": "Available",
                "car_present": False
            })
    print("Slots initialized.")


# --- API ENDPOINTS ---
@app.route('/api/slots', methods=['GET'])
def get_all_slots():
    """For the Streamlit App: Get status of all slots."""
    slots = list(collection.find({}, {"_id": 0}))
    return jsonify(slots)

@app.route('/api/status/<slot_id>', methods=['GET'])
def get_slot_status(slot_id):
    """For the ESP32: Get the status for its LED."""
    slot = collection.find_one({"slot_id": slot_id}, {"_id": 0, "status": 1})
    if slot:
        return jsonify(slot)
    return jsonify({"error": "Slot not found"}), 404

@app.route('/api/reserve/<slot_id>', methods=['POST'])
def reserve_slot(slot_id):
    """For the Streamlit App: A user books a slot (Atomic Update)."""
    
    # Atomic operation: find and update in one step
    result = collection.update_one(
        {"slot_id": slot_id, "status": "Available"},
        {"$set": {"status": "Reserved"}}
    )

    if result.modified_count == 1:
        log_status_change(slot_id, "Reserved", "user_booking")  # Log it
        return jsonify({"success": True, "message": f"{slot_id} reserved"})
    else:
        slot = collection.find_one({"slot_id": slot_id})
        if not slot:
            return jsonify({"error": "Slot not found"}), 404
        return jsonify({"success": False, "message": f"{slot_id} is not available"}), 400

@app.route('/api/update_sensor/<slot_id>', methods=['POST'])
def update_sensor(slot_id):
    """For the ESP32: The sensor reports a car's presence (State-Aware)."""
    data = request.json
    car_present = data.get('car_present', False)

    slot = collection.find_one({"slot_id": slot_id})
    if not slot:
        return jsonify({"error": "Slot not found"}), 404

    current_status = slot.get('status')
    new_status = current_status  # Default to no change
    log_now = False  # Flag to control logging

    if car_present:
        if current_status != "Occupied":
            new_status = "Occupied"
            log_now = True  # Log this change
    else:
        # Car is NOT present.
        # Only set to 'Available' IF it's not 'Reserved'.
        if current_status == "Occupied":
            new_status = "Available"
            log_now = True  # Log this change

    # Update the database
    collection.update_one(
        {"slot_id": slot_id},
        {"$set": {
            "car_present": car_present,
            "status": new_status
        }}
    )

    # Log the change *after* it's confirmed
    if log_now:
        log_status_change(slot_id, new_status, "sensor")

    return jsonify({"success": True, "new_status": new_status})


@app.route('/api/admin/set_status/<slot_id>', methods=['POST'])
def admin_set_status(slot_id):
    """FOR ADMIN: Force-set a slot's status."""
    data = request.json
    new_status = data.get('status')

    if not new_status or new_status not in ["Available", "Reserved", "Occupied"]:
        return jsonify({"error": "Invalid status provided"}), 400

    updates = {"status": new_status}
    if new_status == "Occupied":
        updates["car_present"] = True
    elif new_status == "Available":
        updates["car_present"] = False
    
    collection.update_one(
        {"slot_id": slot_id},
        {"$set": updates}
    )
    
    log_status_change(slot_id, new_status, "admin")  # Log it
    
    return jsonify({"success": True, "message": f"Slot {slot_id} set to {new_status}"})


# --- ML ENDPOINT 1: HISTORICAL ANALYSIS ---

@app.route('/api/ml/rush_hours', methods=['GET'])
def get_rush_hours():
    """
    Analyzes the 'parking_log' collection to find rush hours and busiest days.
    """
    try:
        logs = list(log_collection.find({"status": "Occupied"}))
        
        if len(logs) < 10:  # Not enough data
            return jsonify({"error": "Not enough data to analyze yet."}), 400

        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        df['hour'] = df.index.hour
        df['day_of_week'] = df.index.day_name()

        hourly_counts = df.groupby('hour').size()
        peak_hour = int(hourly_counts.idxmax()) 

        daily_counts = df.groupby('day_of_week').size()
        days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        daily_counts = daily_counts.reindex(days_order, fill_value=0)
        busiest_day = daily_counts.idxmax()

        return jsonify({
            "success": True,
            "hourly_activity": hourly_counts.to_dict(),
            "daily_activity": daily_counts.to_dict(),
            "peak_hour": peak_hour,
            "busiest_day": busiest_day,
            "total_logs": len(logs)
        })

    except Exception as e:
        return jsonify({"error": json_util.dumps(str(e))}), 500


# --- ML ENDPOINT 2: FUTURE FORECASTING (PROPHET) ---

@app.route('/api/ml/get_forecast', methods=['GET'])
def get_forecast():
    """
    Trains a Prophet model on the fly and returns a 48-hour forecast.
    """
    try:
        # 1. Get all parking events (timestamps only)
        logs = list(log_collection.find(
            {"status": "Occupied"}, 
            {"timestamp": 1} 
        ))
        
        if len(logs) < 50: # Need a good amount of data
            return jsonify({"error": "Not enough data to train a model. Need at least 50 events."}), 400

        # 2. Pre-process data for Prophet
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Resample data to get counts per hour
        df.set_index('timestamp', inplace=True)
        df_resampled = df.resample('h').size().reset_index() # 'h' for hourly
        df_resampled.columns = ['ds', 'y'] # Prophet requires 'ds' and 'y'
        
        # 3. Train the model
        m = Prophet(weekly_seasonality=True, daily_seasonality=True)
        m.fit(df_resampled)
        
        # 4. Generate a forecast for the next 2 days (48 hours)
        future = m.make_future_dataframe(periods=48, freq='h')
        forecast = m.predict(future)
        
        # 5. Send the forecast data
        forecast_data = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
        
        # Convert 'ds' (timestamps) to strings for JSON
        forecast_data['ds'] = forecast_data['ds'].astype(str)
        
        return jsonify({
            "success": True,
            "forecast": forecast_data.to_dict('records') # Send as a list of objects
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- RUN THE APP ---
if __name__ == '__main__':
    initialize_slots()
    # Run on 0.0.0.0 to be accessible on your network
    # Set debug=False for production
    app.run(host='0.0.0.0', port=5000, debug=True)