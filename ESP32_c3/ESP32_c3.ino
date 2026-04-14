#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "United";
const char* password = "12345678";

WebServer server(80);

// ----------------------- DUMMY BPM LOGIC ------------------------
int generateDummyBPM() {
  int chance = random(1, 100);  // 1–100

  if (chance <= 100) {
    // 70% normal / resting
    return random(69, 85);
  } else {
    // 30% elevated / stressed
    return random(90, 100);
  }
}

// ----------------------- DATA ENDPOINT -----------------------
void handleData() {
  int gsrValue = analogRead(1);     // GSR sensor on ADC pin
  int bpmValue = generateDummyBPM();

  // ------- SERIAL OUTPUT (DEBUG) -------
  Serial.print("Sending -> BPM: ");
  Serial.print(bpmValue);
  Serial.print(" | GSR: ");
  Serial.println(gsrValue);

  // ------- JSON RESPONSE -------
  String json = "{";
  json += "\"bpm\":" + String(bpmValue) + ",";
  json += "\"gsr\":" + String(gsrValue);
  json += "}";

  server.send(200, "application/json", json);
}

// ----------------------- ROOT PAGE -----------------------
void handleRoot() {
  server.send(200, "text/plain", "ESP32 Dummy Stress Monitor Running");
}

// ----------------------- SETUP -----------------------
void setup() {
  Serial.begin(115200);
  delay(500);

  WiFi.begin(ssid, password);
  Serial.print("Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected!");
  Serial.print("Visit: http://");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.on("/data", handleData);
  server.begin();

  Serial.println("Web server started.");
}

// ----------------------- LOOP -----------------------
void loop() {
  server.handleClient();
}