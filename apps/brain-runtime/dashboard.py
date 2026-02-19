"""
Sage Dashboard - Simplified
Shows live status, transcripts, and chat in a clean interface.
"""

import gradio as gr
import paho.mqtt.client as mqtt
import json
import time
import queue
import os
import uuid
from datetime import datetime
from collections import deque

# Configuration
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
CHAT_REQUEST_TOPIC = os.getenv("SAGE_BRAIN_CHAT_REQUEST_TOPIC", "sage/brain/chat/request")
CHAT_RESPONSE_TOPIC = os.getenv("SAGE_BRAIN_CHAT_RESPONSE_TOPIC", "sage/brain/chat/response")

# Global State
response_queue = queue.Queue()
transcript_log = deque(maxlen=50)  # Keep last 50 transcripts

class SystemStatus:
    def __init__(self):
        self.stt_status = "offline"
        self.brain_status = "offline" # starting, ready
        self.tts_status = "idle"
        self.audio_level = 0.0
        self.speaker_verified = None
        self.last_transcript = ""
        self.last_response = ""
        self.last_rejected_reason = None
        self.stt_ms = 0
        self.total_ms = 0
        self.request_start = None

status = SystemStatus()

# --- MQTT ---
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    client.subscribe("sage/#")
    print(f"[Dashboard] Connected to MQTT")

def on_message(client, userdata, msg):
    global status, transcript_log
    
    topic = msg.topic
    try:
        payload = msg.payload.decode()
    except:
        return
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Brain Status
    if topic == "sage/brain/status":
        try:
            data = json.loads(payload)
            status.brain_status = data.get("status", "unknown")
        except:
            pass

    # STT Status
    elif topic == "sage/stt/status":
        try:
            data = json.loads(payload)
            status.stt_status = data.get("status", "unknown")
            if data.get("status") == "rejected":
                status.last_rejected_reason = data.get("reason", "unknown")
                transcript_log.append(f"[{timestamp}] 🚫 Voice rejected: {status.last_rejected_reason}")
        except:
            pass
            
    # STT Levels (Visualization)
    elif topic == "sage/stt/levels":
        try:
            data = json.loads(payload)
            status.audio_level = data.get("vis", 0.0)
        except:
            pass

    # STT Metrics
    elif topic == "sage/stt/metrics":
        try:
            data = json.loads(payload)
            status.stt_ms = data.get("transcribe_ms", 0)
        except:
            pass
            
    # Voice Transcript
    elif topic == "sage/voice/transcript":
        status.last_transcript = payload
        status.request_start = time.time()
        transcript_log.append(f"[{timestamp}] 🎤 You: {payload}")
        
    # Voice Response
    elif topic == "sage/voice/response":
        try:
            data = json.loads(payload)
            # Ignore chunked streaming packets to avoid duplicate/split transcript lines.
            if data.get("stream"):
                return
            text = data.get("text", "")
            # If text is empty, fallback to raw payload but clean it
            if not text:
                text = payload
        except:
            # If JSON parsing fails, treat as plain text
            text = payload

        # Additional safety: If text looks like JSON, try to extract the "text" field
        if text and text.strip().startswith("{"):
            try:
                json_obj = json.loads(text)
                if "text" in json_obj:
                    text = json_obj["text"]
            except:
                pass  # Keep original text if extraction fails

        if text:
            status.last_response = text
            if status.request_start:
                status.total_ms = int((time.time() - status.request_start) * 1000)
            transcript_log.append(f"[{timestamp}] 🧠 Sage: {text}")
            response_queue.put(text)
    elif topic == CHAT_RESPONSE_TOPIC:
        try:
            data = json.loads(payload)
            if not data.get("success", True):
                text = f"Error: {data.get('error', 'unknown error')}"
            else:
                text = data.get("text", "")
        except Exception:
            text = payload

        if text:
            status.last_response = text
            if status.request_start:
                status.total_ms = int((time.time() - status.request_start) * 1000)
            transcript_log.append(f"[{timestamp}] 🧠 Sage: {text}")
            response_queue.put(text)
            
    # TTS Status
    elif topic == "sage/tts/status":
        try:
            data = json.loads(payload)
            status.tts_status = data.get("status", "idle")
        except:
            pass

client.on_connect = on_connect
client.on_message = on_message

def start_mqtt():
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"MQTT Connect Failed: {e}")

# --- UI Helpers ---

def get_big_status():
    """Get the main status indicator."""
    s = status.stt_status
    b = status.brain_status
    t = status.tts_status
    
    # Brain Priority (Must be ready)
    if b == "starting":
        return "⏳ WARMING UP", "Brain is loading..."
    
    if t == "speaking":
        return "🔊 SPEAKING", "Sage is talking..."
    elif s == "hearing":
        return "👂 HEARING", "Listening to you..."
    elif s == "processing":
        return "⚙️ THINKING", "Processing your speech..."
    elif s == "listening":
        if b == "ready":
            return "🎤 READY", "Waiting for you to speak..."
        else:
            return "⏳ WAITING", "Brain not ready yet..."
    elif s == "rejected":
        return "🚫 REJECTED", f"Voice not recognized"
    elif s == "offline":
        return "⚫ OFFLINE", "STT service not running"
    else:
        return "❓ UNKNOWN", f"{s} / {b}"

def get_transcript_text():
    if not transcript_log:
        return "No transcripts yet. Start talking!"
    return "\n".join(transcript_log)

def get_metrics_text():
    parts = []
    if status.stt_ms:
        parts.append(f"STT: {status.stt_ms}ms")
    if status.total_ms:
        parts.append(f"Total: {status.total_ms}ms")
    return " | ".join(parts) if parts else "—"

def get_audio_vis():
    """Return a visual bar for audio level."""
    # Create a simple ASCII bar
    blocks = " ▂▃▅▇"
    # Level is 0.0 to 1.0. Map to 0-10 chars
    val = int(status.audio_level * 10)
    if val == 0:
        return ""
    
    bar = ""
    for i in range(10):
        if i < val:
            bar += "▇"
        else:
            bar += " "
    return bar

def refresh_all():
    emoji, text = get_big_status()
    return (
        emoji,
        text,
        get_transcript_text(),
        get_metrics_text(),
        get_audio_vis()
    )

# --- Chat Logic ---

def send_message(msg, history):
    """Send a text message to Sage."""
    if not msg.strip():
        return "", history
    
    # Add user message
    history.append({"role": "user", "content": msg})
    
    # Clear response queue
    with response_queue.mutex:
        response_queue.queue.clear()
    
    # Send to brain chat RPC (direct brain test path, bypasses voice suppression rules)
    status.request_start = time.time()
    request_id = str(uuid.uuid4())
    payload = {
        "request_id": request_id,
        "conversation_id": "dashboard",
        "text": msg,
        "reason": "user_intent",
        "response_topic": CHAT_RESPONSE_TOPIC,
    }
    client.publish(CHAT_REQUEST_TOPIC, json.dumps(payload))
    transcript_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 💬 You: {msg}")
    
    # Wait for response
    history.append({"role": "assistant", "content": "..."})
    
    return "", history

def get_response(history):
    """Poll for Sage's response."""
    if not history or history[-1].get("role") != "assistant":
        yield history
        return
    
    start = time.time()
    while time.time() - start < 30:
        try:
            resp = response_queue.get(timeout=0.2)
            history[-1]["content"] = resp
            yield history
            return
        except queue.Empty:
            yield history
    
    history[-1]["content"] = "⏱️ Timeout waiting for response"
    yield history

# --- Dashboard UI ---

# Custom CSS to fix contrast issues
CUSTOM_CSS = """
/* Fix white-on-white text issues */
.gradio-container input[type="text"],
.gradio-container textarea,
.gradio-container .gr-textbox input,
.gradio-container .gr-textbox textarea {
    color: var(--body-text-color) !important;
    background-color: var(--input-background-fill) !important;
}

/* Ensure status textboxes are readable */
.gr-textbox input:disabled,
.gr-textbox textarea:disabled {
    color: var(--body-text-color) !important;
    opacity: 1 !important;
}

/* Big status emoji styling */
.big-status input {
    font-size: 2em !important;
    text-align: center !important;
}

/* Transcript log readability */
#transcript_box textarea {
    font-family: monospace !important;
    font-size: 0.9em !important;
}
"""

def create_dashboard():
    with gr.Blocks(title="Sage") as demo:
        
        # Header with big status
        gr.Markdown("# 🧠 Sage")
        
        with gr.Row():
            status_emoji = gr.Textbox(
                value="⚫",
                label="",
                interactive=False,
                scale=1,
                min_width=100,
                elem_classes=["big-status"]
            )
            status_text = gr.Textbox(
                value="Starting...",
                label="Status",
                interactive=False,
                scale=3
            )
            metrics_text = gr.Textbox(
                value="—",
                label="Latency",
                interactive=False,
                scale=2
            )
            # Volume visualizer
            audio_bar = gr.Textbox(
                value="",
                label="Audio Input",
                interactive=False, 
                max_lines=1,
                scale=3
            )
            
            live_toggle = gr.Checkbox(
                value=True,
                label="Live Updates",
                interactive=True,
                scale=1
            )
        
        with gr.Tabs():
            # Tab 1: Live Feed
            with gr.TabItem("📜 Live"):
                gr.Markdown("### What Sage hears and says")
                transcript_box = gr.Textbox(
                    value=get_transcript_text(),
                    label="Transcript Log",
                    lines=15,
                    max_lines=20,
                    interactive=False,
                    elem_id="transcript_box"
                )
                refresh_btn = gr.Button("🔄 Refresh")
                
            # Tab 2: Chat
            with gr.TabItem("💬 Chat"):
                chatbot = gr.Chatbot(height=350, label="")
                
                with gr.Row():
                    msg_input = gr.Textbox(
                        placeholder="Type a message...",
                        show_label=False,
                        scale=4
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)
                
                clear_btn = gr.Button("🗑️ Clear")
            
            # Tab 3: Settings (simplified)
            with gr.TabItem("⚙️ Settings"):
                gr.Markdown("### Personality")
                
                with gr.Row():
                    personality_select = gr.Dropdown(
                        [
                            ("Sage - Afro-Caribbean Therapist", "sage"),
                            ("HomeBuddy - Kenyan Babe", "kenyan_babe"),
                            ("Martin - Systems Builder", "martin")
                        ],
                        value="kenyan_babe",
                        label="Personality",
                        info="Who should Sage be?"
                    )
                    personality_btn = gr.Button("Switch", variant="secondary")
                
                personality_status = gr.Textbox(label="", interactive=False, max_lines=1)
                
                def switch_personality(personality):
                    client.publish("sage/brain/config", json.dumps({
                        "personality": personality
                    }))
                    names = {
                        "sage": "Sage (Afro-Caribbean Therapist)",
                        "kenyan_babe": "HomeBuddy (Kenyan Babe)",
                        "martin": "Martin (Systems Builder)"
                    }
                    return f"✓ Switched to: {names.get(personality, personality)}"
                
                personality_btn.click(
                    switch_personality,
                    [personality_select],
                    personality_status
                )
                
                gr.Markdown("---")
                gr.Markdown("### Voice Settings")
                
                with gr.Row():
                    voice_select = gr.Dropdown(
                        ["af_bella", "af_sarah", "am_michael", "am_adam", "bf_emma"],
                        value="af_bella",
                        label="Voice"
                    )
                    speed_slider = gr.Slider(0.7, 1.3, value=1.0, step=0.1, label="Speed")
                
                gr.Markdown("### Detection Settings")
                
                silence_slider = gr.Slider(
                    0.3, 1.5, value=0.7, step=0.1,
                    label="Pause Detection (seconds)",
                    info="How long to wait after you stop talking"
                )
                
                apply_btn = gr.Button("Apply Settings", variant="primary")
                settings_status = gr.Textbox(label="", interactive=False)
                
                def apply_settings(voice, speed, silence):
                    # Voice config
                    client.publish("sage/voice/config", json.dumps({
                        "voice": voice,
                        "speed": speed
                    }))
                    # Performance config
                    client.publish("sage/config/performance", json.dumps({
                        "silence_duration": silence
                    }))
                    return f"✓ Applied: {voice}, {speed}x speed, {silence}s pause"
                
                apply_btn.click(
                    apply_settings,
                    [voice_select, speed_slider, silence_slider],
                    settings_status
                )
                
                gr.Markdown("---")
                gr.Markdown("### Memory")
                
                with gr.Row():
                    clear_convo_btn = gr.Button("Clear Current Conversation", variant="secondary")
                    clear_memory_btn = gr.Button("Clear All Memory", variant="stop")
                
                memory_status = gr.Textbox(label="", interactive=False, max_lines=1)
                
                def clear_conversation():
                    client.publish("sage/brain/command", json.dumps({
                        "command": "clear_conversation"
                    }))
                    return "✓ Conversation cleared (saved to long-term memory)"
                
                def clear_all_memory():
                    client.publish("sage/brain/command", json.dumps({
                        "command": "clear_memory"
                    }))
                    return "✓ All memory cleared"
                
                clear_convo_btn.click(clear_conversation, None, memory_status)
                clear_memory_btn.click(clear_all_memory, None, memory_status)
        
        # Event handlers
        refresh_btn.click(
            refresh_all,
            None,
            [status_emoji, status_text, transcript_box, metrics_text, audio_bar]
        )
        
        msg_input.submit(
            send_message, [msg_input, chatbot], [msg_input, chatbot]
        ).then(
            get_response, chatbot, chatbot
        ).then(
            refresh_all, None, [status_emoji, status_text, transcript_box, metrics_text, audio_bar]
        )
        
        send_btn.click(
            send_message, [msg_input, chatbot], [msg_input, chatbot]
        ).then(
            get_response, chatbot, chatbot
        ).then(
            refresh_all, None, [status_emoji, status_text, transcript_box, metrics_text, audio_bar]
        )
        
        clear_btn.click(lambda: [], None, chatbot)
        
        # Store last known values for when live mode is off
        last_values = {"emoji": "⚫", "text": "—", "transcript": "", "metrics": "—", "audio": ""}
        
        def conditional_refresh(is_live):
            """Only refresh if live mode is enabled."""
            if is_live:
                result = refresh_all()
                # Cache the values
                last_values["emoji"] = result[0]
                last_values["text"] = result[1]
                last_values["transcript"] = result[2]
                last_values["metrics"] = result[3]
                last_values["audio"] = result[4]
                return result
            else:
                # Return last known values (no update)
                return (
                    last_values["emoji"],
                    last_values["text"],
                    last_values["transcript"],
                    last_values["metrics"],
                    last_values["audio"]
                )
        
        # Initial load (always run once)
        demo.load(
            refresh_all,
            None,
            [status_emoji, status_text, transcript_box, metrics_text, audio_bar]
        )
        
        # Periodic refresh - only updates when live mode is ON
        # Use Timer for Gradio 4.0+ (we are on 6.x)
        timer = gr.Timer(0.2)  # Slightly slower to reduce CPU usage
        timer.tick(
            conditional_refresh,
            [live_toggle],
            [status_emoji, status_text, transcript_box, metrics_text, audio_bar]
        )
    
    return demo


if __name__ == "__main__":
    start_mqtt()
    app = create_dashboard()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        css=CUSTOM_CSS,
        theme=gr.themes.Soft()
    )
