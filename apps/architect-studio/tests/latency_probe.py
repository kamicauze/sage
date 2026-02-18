
import time
import json
import sys
import uuid
import paho.mqtt.client as mqtt

MQTT_HOST = "localhost"
MQTT_PORT = 1883

class LatencyProbe:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.response_received = False
        self.start_time = 0
        self.end_time = 0
        self.test_message = "What is the capital of Kenya?"
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"[Probe] Connected to MQTT (rc={rc})")
        client.subscribe("sage/voice/response")
        
        # Calculate start time right before publish for accuracy
        print(f"[Probe] Sending: '{self.test_message}'")
        self.start_time = time.time()
        client.publish("sage/voice/transcript", self.test_message)
        
    def on_message(self, client, userdata, msg):
        payload_str = msg.payload.decode()
        try:
            data = json.loads(payload_str)
            text = data.get("text", "")
            # Verify it's a response (some responses might be empty or keep-alives)
            if text:
                self.end_time = time.time()
                self.response_received = True
                
                latency_ms = (self.end_time - self.start_time) * 1000
                print(f"\n[Probe] Response Received!")
                print(f"Message: {text[:100]}...")
                print(f"Latency: {latency_ms:.2f} ms")
                
                client.disconnect()
        except Exception as e:
            print(f"[Probe] Error parsing response: {e}")

    def run(self):
        try:
            self.client.connect(MQTT_HOST, MQTT_PORT, 60)
            self.client.loop_start()
            
            # Wait for response with timeout
            timeout = 60 # seconds
            waited = 0
            while not self.response_received and waited < timeout:
                time.sleep(0.1)
                waited += 0.1
                
            if not self.response_received:
                print(f"\n[Probe] Timeout ({timeout}s) - No response received.")
                print("Make sure Sage Brain is running: './sage brain'")
                
            self.client.loop_stop()
            
        except Exception as e:
            print(f"[Probe] Connection Failed: {e}")

if __name__ == "__main__":
    probe = LatencyProbe()
    probe.run()
