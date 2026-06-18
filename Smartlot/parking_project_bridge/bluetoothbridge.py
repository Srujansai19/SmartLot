import serial
import requests
import time
import threading

# --- CONFIGURATION ---
# 1. Find this after pairing your ESP32 with your laptop
#    - On Windows: Check Device Manager (e.g., "COM3", "COM4")
#    - On Mac: In terminal, run 'ls /dev/tty.*' (e.g., "/dev/tty.ESP32_Parking_Sensor")
#    - On Linux: In terminal, run 'ls /dev/rfcomm*' (e.g., "/dev/rfcomm0")
SERIAL_PORT = "COM5"  # e.g., "COM3"
BAUD_RATE = 115200

# This is your Flask server, running on the same laptop
FLASK_URL = "http://127.0.0.1:5000/api"
SLOT_ID = "A1" # This bridge only manages A1
SYNC_INTERVAL = 3 # Fetch status from Flask every 3 seconds
# ---------------------

def init_serial():
    """Tries to connect to the serial port."""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Successfully connected to {SERIAL_PORT}")
        return ser
    except serial.SerialException as e:
        print(f"Error: Could not open port {SERIAL_PORT}.")
        print("Please check:")
        print(" 1. Is the ESP32 paired with your laptop?")
        print(" 2. Is the SERIAL_PORT variable correct?")
        print(" 3. Is the ESP32 powered on?")
        print(f"Details: {e}")
        return None

def listen_for_esp_updates(ser):
    """
    Listens for SENSOR updates from the ESP32 and posts them to Flask.
    This runs in its own thread.
    """
    while True:
        try:
            if ser.in_waiting:
                # Read a line from the ESP32
                line = ser.readline().decode('utf-8').strip()
                
                if line.startswith("SENSOR,"):
                    print(f"Received from ESP32: {line}")
                    
                    # Parse the message: "SENSOR,A1,true"
                    parts = line.split(',')
                    if len(parts) == 3:
                        slot_id, car_present_str = parts[1], parts[2]
                        car_present = True if car_present_str == 'true' else False
                        
                        # Send this update to the Flask API
                        payload = {"car_present": car_present}
                        try:
                            r = requests.post(f"{FLASK_URL}/update_sensor/{slot_id}", json=payload)
                            if r.status_code == 200:
                                print(f"Successfully updated Flask: {slot_id} -> {payload}")
                            else:
                                print(f"Error updating Flask: {r.status_code}")
                        except requests.ConnectionError:
                            print("Error: Flask server not reachable.")
                            
        except Exception as e:
            print(f"Error in listener thread: {e}")
            time.sleep(1) # Avoid spamming errors

def sync_flask_to_esp(ser):
    """
    Periodically gets the "source of truth" status from Flask
    and sends it to the ESP32 to update its LEDs.
    This runs in the main thread.
    """
    while True:
        try:
            # Get the official status from Flask
            r = requests.get(f"{FLASK_URL}/status/{SLOT_ID}")
            if r.status_code == 200:
                status = r.json().get('status', 'Available')
                
                # Send the status (e.g., "Reserved") to the ESP32
                print(f"Syncing to ESP32: Status is {status}")
                ser.write(f"{status}\n".encode('utf-8'))
            else:
                print(f"Error syncing from Flask: {r.status_code}")
                
        except requests.ConnectionError:
            print("Error: Flask server not reachable for sync.")
        except Exception as e:
            print(f"Error in sync task: {e}")
            
        time.sleep(SYNC_INTERVAL)

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    ser = init_serial()
    
    if ser:
        print("Starting 2-way sync bridge...")
        
        # Start the ESP32 listener in a separate thread
        listener_thread = threading.Thread(target=listen_for_esp_updates, args=(ser,), daemon=True)
        listener_thread.start()
        
        # Start the Flask-to-ESP32 sync in the main thread
        sync_flask_to_esp(ser)