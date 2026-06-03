#include <SPI.h>
#include <Ethernet.h>

// ============================================================================
// Configuration
// ============================================================================
byte mac[] = {0xA8, 0x61, 0x0A, 0xAE, 0x84, 0xDA};
IPAddress ip(10, 20, 30, 47);
EthernetServer server(80);

// Pin assignments
const int PIN_LAMP = 7;
const int PIN_AVANTES = 8;

// Timing configuration
const unsigned int PULSE_WIDTH_US = 10;      // Pulse width in microseconds
const unsigned long PULSE_INTERVAL_MS = 25;  // 25ms = 40Hz
const unsigned long CLIENT_TIMEOUT_MS = 1000; // HTTP client timeout

// ============================================================================
// State variables
// ============================================================================
bool ttl_lamp_enabled = false;
bool ttl_avantes_enabled = false;
unsigned long last_pulse_time = 0;
unsigned long pulse_count = 0;

// ============================================================================
// Setup
// ============================================================================
void setup() {
  // Initialize outputs
  pinMode(PIN_LAMP, OUTPUT);
  pinMode(PIN_AVANTES, OUTPUT);
  digitalWrite(PIN_LAMP, LOW);
  digitalWrite(PIN_AVANTES, LOW);
  
  // Initialize Ethernet
  Ethernet.begin(mac, ip);
  server.begin();
  
  // Serial for debugging
  Serial.begin(9600);
  Serial.print(F("TTL Controller ready at: "));
  Serial.println(Ethernet.localIP());
}

// ============================================================================
// Non-blocking TTL pulse generation
// ============================================================================
void ttl_generate_nonblocking() {
  // Skip if nothing enabled
  if (!ttl_lamp_enabled && !ttl_avantes_enabled) return;
  
  unsigned long now = millis();
  if (now - last_pulse_time >= PULSE_INTERVAL_MS) {
    last_pulse_time = now;
    pulse_count++;
    
    // Generate pulse
    if (ttl_lamp_enabled) digitalWrite(PIN_LAMP, HIGH);
    if (ttl_avantes_enabled) digitalWrite(PIN_AVANTES, HIGH);
    
    delayMicroseconds(PULSE_WIDTH_US);  // 10us blocking is acceptable
    
    digitalWrite(PIN_LAMP, LOW);
    digitalWrite(PIN_AVANTES, LOW);
  }
}

// ============================================================================
// Get current mode as string
// ============================================================================
const char* get_mode_string() {
  if (ttl_lamp_enabled && ttl_avantes_enabled) return "LAMP + AVANTES";
  if (ttl_avantes_enabled) return "AVANTES ONLY";
  return "OFF";
}

// ============================================================================
// Send HTML response
// ============================================================================
void send_html_response(EthernetClient& client) {
  // HTTP headers
  client.println(F("HTTP/1.1 200 OK"));
  client.println(F("Content-Type: text/html"));
  client.println(F("Connection: close"));
  client.println();
  
  // HTML with embedded CSS for nice UI
  client.println(F("<!DOCTYPE html><html><head>"));
  client.println(F("<meta name='viewport' content='width=device-width,initial-scale=1'>"));
  client.println(F("<title>TTL Trigger Controller</title>"));
  client.println(F("<style>"));
  client.println(F("*{box-sizing:border-box;font-family:Arial,sans-serif}"));
  client.println(F("body{background:#1a1a2e;color:#eee;margin:0;padding:20px}"));
  client.println(F(".container{max-width:500px;margin:0 auto}"));
  client.println(F("h1{color:#0f0;text-align:center;border-bottom:2px solid #0f0;padding-bottom:10px}"));
  client.println(F(".status{background:#16213e;padding:20px;border-radius:10px;margin:20px 0}"));
  client.println(F(".status-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #333}"));
  client.println(F(".label{color:#888}"));
  client.println(F(".on{color:#0f0;font-weight:bold}"));
  client.println(F(".off{color:#f44;font-weight:bold}"));
  client.println(F(".mode{font-size:1.3em;text-align:center;padding:15px;background:#0f3460;border-radius:8px;margin:15px 0}"));
  client.println(F(".buttons{display:flex;flex-direction:column;gap:10px;margin-top:20px}"));
  client.println(F("button{padding:15px;font-size:1.1em;border:none;border-radius:8px;cursor:pointer;transition:0.2s}"));
  client.println(F(".btn-sample{background:#4CAF50;color:#fff}"));
  client.println(F(".btn-sample:hover{background:#45a049}"));
  client.println(F(".btn-bg{background:#2196F3;color:#fff}"));
  client.println(F(".btn-bg:hover{background:#1976D2}"));
  client.println(F(".btn-off{background:#f44336;color:#fff}"));
  client.println(F(".btn-off:hover{background:#d32f2f}"));
  client.println(F(".info{background:#0f3460;padding:15px;border-radius:8px;margin-top:20px;font-size:0.9em}"));
  client.println(F(".info p{margin:5px 0;color:#aaa}"));
  client.println(F("</style></head><body>"));
  
  // Content
  client.println(F("<div class='container'>"));
  client.println(F("<h1>TTL Trigger Controller</h1>"));
  
  // Status panel
  client.println(F("<div class='status'>"));
  
  // Current mode
  client.print(F("<div class='mode'>Mode: <strong>"));
  client.print(get_mode_string());
  client.println(F("</strong></div>"));
  
  // Lamp status
  client.print(F("<div class='status-row'><span class='label'>Flash Lamp (Pin 7)</span><span class='"));
  client.print(ttl_lamp_enabled ? F("on'>ON") : F("off'>OFF"));
  client.println(F("</span></div>"));
  
  // Avantes status
  client.print(F("<div class='status-row'><span class='label'>Avantes (Pin 8)</span><span class='"));
  client.print(ttl_avantes_enabled ? F("on'>ON") : F("off'>OFF"));
  client.println(F("</span></div>"));
  
  // Pulse count
  client.print(F("<div class='status-row'><span class='label'>Pulses Generated</span><span>"));
  client.print(pulse_count);
  client.println(F("</span></div>"));
  
  client.println(F("</div>"));
  
  // Control buttons
  client.println(F("<form class='buttons'>"));
  client.println(F("<button type='submit' name='status' value='LAMP AND AVANTES' class='btn-sample'>Sample Mode (Lamp + Avantes)</button>"));
  client.println(F("<button type='submit' name='status' value='ONLY AVANTES' class='btn-bg'>Background Mode (Avantes Only)</button>"));
  client.println(F("<button type='submit' name='status' value='OFF' class='btn-off'>Stop All</button>"));
  client.println(F("</form>"));
  
  // Info panel
  client.println(F("<div class='info'>"));
  client.print(F("<p>Frequency: "));
  client.print(1000 / PULSE_INTERVAL_MS);
  client.println(F(" Hz</p>"));
  client.print(F("<p>Pulse width: "));
  client.print(PULSE_WIDTH_US);
  client.println(F(" us</p>"));
  client.print(F("<p>IP: "));
  client.print(Ethernet.localIP());
  client.println(F("</p>"));
  client.println(F("</div>"));
  
  client.println(F("</div></body></html>"));
}

// ============================================================================
// Handle HTTP client requests
// ============================================================================
void handle_client() {
  EthernetClient client = server.available();
  if (!client) return;
  
  // Only store first line of HTTP request (GET /path?params)
  char request_line[128];
  int line_idx = 0;
  bool first_line_done = false;
  bool headers_complete = false;
  int newline_count = 0;
  unsigned long timeout = millis() + CLIENT_TIMEOUT_MS;
  
  while (client.connected() && millis() < timeout) {
    // Keep generating pulses while handling request
    ttl_generate_nonblocking();
    
    if (client.available()) {
      char c = client.read();
      
      // Store only the first line (contains GET request with params)
      if (!first_line_done) {
        if (c == '\r' || c == '\n') {
          first_line_done = true;
          request_line[line_idx] = '\0';
        } else if (line_idx < sizeof(request_line) - 1) {
          request_line[line_idx++] = c;
        }
      }
      
      // Detect end of headers (\r\n\r\n)
      if (c == '\n') {
        newline_count++;
        if (newline_count >= 2) {
          headers_complete = true;
          break;
        }
      } else if (c != '\r') {
        newline_count = 0;
      }
    }
  }
  
  if (headers_complete) {
    // Parse command from GET request line
    if (strstr(request_line, "status=LAMP+AND+AVANTES")) {
      ttl_lamp_enabled = true;
      ttl_avantes_enabled = true;
      pulse_count = 0;
      Serial.println(F("Mode: LAMP + AVANTES"));
    } 
    else if (strstr(request_line, "status=ONLY+AVANTES")) {
      ttl_lamp_enabled = false;
      ttl_avantes_enabled = true;
      pulse_count = 0;
      Serial.println(F("Mode: AVANTES ONLY"));
    } 
    else if (strstr(request_line, "status=OFF")) {
      ttl_lamp_enabled = false;
      ttl_avantes_enabled = false;
      Serial.println(F("Mode: OFF"));
    }
    
    // Send response
    send_html_response(client);
  }
  
  delay(1);  // Brief delay for client to receive data
  client.stop();
}

// ============================================================================
// Main loop - non-blocking
// ============================================================================
void loop() {
  ttl_generate_nonblocking();  // Generate pulses (never blocks)
  handle_client();             // Handle web requests (with timeout)
}
