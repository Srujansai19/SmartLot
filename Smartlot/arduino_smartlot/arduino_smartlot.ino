/*
 * ==========================================================
 * ==         FULL SMART PARKING SYSTEM - 4 SLOTS          ==
 * ==========================================================
 * This code connects to WiFi and syncs with the Flask backend.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- USER CONFIGURATION ---
// const char* WIFI_SSID = "SOE III";
// const char* WIFI_PASS = "mruh@soe3";
const char* WIFI_SSID = "network";
const char* WIFI_PASS = "12345678";
// const char* WIFI_SSID = "4884";
// const char* WIFI_PASS = "password123";


// const char* BACKEND_URL = "http://15.20.17.223:5000";
// const char* BACKEND_URL = "http://192.168.29.176:5000";
// const char* BACKEND_URL = "http://15.20.71.7:5000";
const char* BACKEND_URL = "http://192.168.137.54:5000";

// ----------------------------

// --- PIN DEFINITIONS (Match our full circuit plan) ---
const int SLOTS = 4;


const int TRIG_PINS[] = {25, 27, 14, 12}; 
const int ECHO_PINS[] = {26, 34, 36, 35}; 
const int RED_PINS[]  = {19, 33, 23, 13};
const int YLW_PINS[]  = {18, 32, 22, 15};
const int GRN_PINS[]  = {5,  4,  21, 2 }; 

const char* SLOT_IDS[] = {"A1", "A2", "A3", "A4"};

const int OCCUPIED_DISTANCE = 15; // cm
bool lastCarState[] = {false, false, false, false};

// --- WiFi Setup ---
void setupWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

// --- Pin Setup ---
void setupPins() {
  for (int i = 0; i < SLOTS; i++) {
    pinMode(TRIG_PINS[i], OUTPUT);
    pinMode(ECHO_PINS[i], INPUT);
    pinMode(RED_PINS[i], OUTPUT);
    pinMode(YLW_PINS[i], OUTPUT);
    pinMode(GRN_PINS[i], OUTPUT);
    // Set all to Green initially
    digitalWrite(RED_PINS[i], LOW);
    digitalWrite(YLW_PINS[i], LOW);
    digitalWrite(GRN_PINS[i], HIGH);
  }
}

// --- Main Setup ---
void setup() {
  Serial.begin(115200);
  Serial.println("Parking System Booting Up...");
  setupPins();
  setupWiFi();
  Serial.println("Setup complete.");
}

// --- MAIN LOOP ---
void loop() {
  for (int i = 0; i < SLOTS; i++) {
    // 1. Check the sensor
    bool carPresent = isCarPresent(i);

    // 2. If state *changed*, update the backend
    if (carPresent != lastCarState[i]) {
      updateBackendSensor(SLOT_IDS[i], carPresent);
      lastCarState[i] = carPresent;
    }

    // 3. Get the latest status from backend
    String status = getSlotStatus(SLOT_IDS[i]);

    // 4. Set the LEDs based on status
    setLEDs(i, status);

    delay(200); // Small delay between checking each slot
  }
  delay(2000); // Wait 2 seconds before checking all slots again
}

// --- HELPER FUNCTIONS ---

bool isCarPresent(int slotIndex) {
  digitalWrite(TRIG_PINS[slotIndex], LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PINS[slotIndex], HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PINS[slotIndex], LOW);

  long duration = pulseIn(ECHO_PINS[slotIndex], HIGH, 30000); // 30ms timeout
  int distance = duration * 0.034 / 2;

  return (distance < OCCUPIED_DISTANCE && distance > 0);
}

void updateBackendSensor(const char* slotId, bool carPresent) {
  HTTPClient http;
  String url = String(BACKEND_URL) + "/api/update_sensor/" + String(slotId);
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  // Create JSON payload
  String payload = "{\"car_present\": " + String(carPresent ? "true" : "false") + "}";
  
  Serial.printf("Updating %s: %s\n", slotId, payload.c_str());
  int httpCode = http.POST(payload);

  if (httpCode > 0) {
    Serial.printf("Update %s response: %d\n", slotId, httpCode);
  } else {
    Serial.printf("Update %s failed: %s\n", slotId, http.errorToString(httpCode).c_str());
  }
  http.end();
}

String getSlotStatus(const char* slotId) {
  HTTPClient http;
  String url = String(BACKEND_URL) + "/api/status/" + String(slotId);
  http.begin(url);

  int httpCode = http.GET();
  if (httpCode == 200) {
    String payload = http.getString();
    
    StaticJsonDocument<128> doc;
    deserializeJson(doc, payload);
    
    const char* status = doc["status"];
    http.end();
    return String(status);
  }
  
  http.end();
  return "Available"; // Default
}

void setLEDs(int slotIndex, String status) {
  if (status == "Occupied") {
    digitalWrite(RED_PINS[slotIndex], HIGH);
    digitalWrite(YLW_PINS[slotIndex], LOW);
    digitalWrite(GRN_PINS[slotIndex], LOW);
  } else if (status == "Reserved") {
    digitalWrite(RED_PINS[slotIndex], LOW);
    digitalWrite(YLW_PINS[slotIndex], HIGH); // Use Yellow for Reserved
    digitalWrite(GRN_PINS[slotIndex], LOW);
  } else { // "Available"
    digitalWrite(RED_PINS[slotIndex], LOW);
    digitalWrite(YLW_PINS[slotIndex], LOW);
    digitalWrite(GRN_PINS[slotIndex], HIGH);
  }
}