import pymongo
import os
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
MONGO_URL = "mongodb+srv://srinivasm0860_db_user:s123@smartlotslots.bjz0jbz.mongodb.net/?appName=Smartlotslots"
if not MONGO_URL:
    print("Error: MONGO_URL environment variable is not set.")
    print("Please set it *in this terminal* before running the script.")
    print("e.g., export MONGO_URL=\"mongodb+srv://...\"")
    exit()

DB_NAME = "smart_parking"
LOG_COLLECTION_NAME = "parking_log"

# --- RUSH HOUR SIMULATION ---
# Weights for each hour of the day (0-23)
# We'll make 8-10am and 5-7pm much busier
HOURS_WEIGHTS = [
  # 12am 1am  2am  3am  4am  5am  6am  7am
     1,   1,   1,   1,   2,   3,   5,   8,
  # 8am  9am 10am 11am 12pm  1pm  2pm  3pm
    10,  10,   8,   7,   7,   6,   6,   7,
  # 4pm  5pm  6pm  7pm  8pm  9pm 10pm 11pm
     8,  10,  10,   8,   6,   4,   3,   2
]

SLOT_IDS = ["A1", "A2", "A3", "A4"]
TOTAL_RECORDS = 2000

# --- MAIN SCRIPT ---
print("Connecting to MongoDB...")
try:
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    log_collection = db[LOG_COLLECTION_NAME]
    print(f"Connected to '{DB_NAME}' database.")
except Exception as e:
    print(f"Could not connect to MongoDB: {e}")
    exit()

# 1. Clear all old logs
print("Clearing old data from 'parking_log'...")
log_collection.delete_many({})
print("Old data cleared.")

# 2. Generate new synthetic data
print(f"Generating {TOTAL_RECORDS} synthetic log entries...")
entries_to_insert = []
for i in range(TOTAL_RECORDS):
    # Pick a random day in the last 90 days
    base_day = datetime.now() - timedelta(days=random.randint(0, 90))
    
    # Pick a biased hour, minute, and second
    hour = random.choices(range(24), weights=HOURS_WEIGHTS, k=1)[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    
    # Create the fake timestamp
    timestamp = base_day.replace(hour=hour, minute=minute, second=second, microsecond=0)
    
    # Create the log entry
    log_entry = {
        "slot_id": random.choice(SLOT_IDS),
        "status": "Occupied",
        "timestamp": timestamp,
        "source": "sensor" # Simulate a sensor event
    }
    entries_to_insert.append(log_entry)

# 3. Insert all records in one go (much faster)
try:
    log_collection.insert_many(entries_to_insert)
    print(f"\nSuccessfully inserted {len(entries_to_insert)} records.")
    print("Your database is now populated with sufficient data!")
except Exception as e:
    print(f"An error occurred during insertion: {e}")

client.close()