
import os
from dotenv import load_dotenv

# Replicate main.py logic
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Check direct env var
xai_key = os.getenv("XAI_API_KEY")
print(f"XAI_API_KEY env var present: {bool(xai_key)}")
if xai_key:
    print(f"XAI_API_KEY starts with: {xai_key[:8]}...")

# Check CloudBrain logic
try:
    from ai.cloud_client import CloudBrain
    brain = CloudBrain()
    print(f"CloudBrain.grok_key present: {bool(brain.grok_key)}")
    if brain.grok_key:
        print(f"CloudBrain.grok_key starts with: {brain.grok_key[:8]}...")
        if brain.grok_key == xai_key:
            print("SUCCESS: CloudBrain picked up XAI_API_KEY")
        else:
            print("WARNING: CloudBrain has different key")
except ImportError:
    print("Could not import CloudBrain (paths might be off)")
except Exception as e:
    print(f"Error initializing CloudBrain: {e}")
