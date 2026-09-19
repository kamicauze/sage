#!/usr/bin/env python3
"""
Sage Symbiote CLI
Unified entry point for the entire Sage system.
Controls Brain, Voice, Architect, and Dashboard.
"""
import argparse
import sys
import os
import json
import subprocess
import signal
import time
from datetime import datetime

# Ensure we can import from local modules
sys.path.append(os.getcwd())

# --- Architect Imports ---
MANIFEST_PATH = "architect/projects/sage.yaml"
ARCH_USAGE_FILE = "architect/usage.json"
ARCH_USAGE_LOG_FILE = "architect/.cache/usage_log.jsonl"
ARCH_UI_DIR = "architect/ui"
ARCH_UI_ENV_LOCAL = f"{ARCH_UI_DIR}/.env.local"
ARCH_UI_ENV_EXAMPLE = f"{ARCH_UI_DIR}/.env.local.example"

try:
    from architect.manifest import ProjectManifest
    from architect.router import ArchitectRouter, BuildRequest
    from architect.ingest import ingest_manifest
    from architect.llm_updater import LLMUpdater
    from architect.paths import (
        project_manifest_path,
        root_relative,
        USAGE_FILE as ARCH_USAGE_FILE_PATH,
        USAGE_LOG_FILE as ARCH_USAGE_LOG_FILE_PATH,
        UI_DIR as ARCH_UI_DIR_PATH,
    )

    MANIFEST_PATH = root_relative(project_manifest_path("sage"))
    ARCH_USAGE_FILE = str(ARCH_USAGE_FILE_PATH)
    ARCH_USAGE_LOG_FILE = str(ARCH_USAGE_LOG_FILE_PATH)
    ARCH_UI_DIR = root_relative(ARCH_UI_DIR_PATH)
    ARCH_UI_ENV_LOCAL = f"{ARCH_UI_DIR}/.env.local"
    ARCH_UI_ENV_EXAMPLE = f"{ARCH_UI_DIR}/.env.local.example"
except ImportError:
    # Allow running basic commands even if architect deps are missing
    pass

# --- Helper Functions ---

def ensure_mosquitto_running():
    """
    Checks if Mosquitto is running with the correct configuration.
    If not, it starts it properly.
    Returns: (process_handle, success_boolean)
    """
    # 1. Check if already running properly
    try:
        # Check specifically for our custom config
        if subprocess.call(["pgrep", "-f", "mosquitto.*mosquitto.conf"], stdout=subprocess.DEVNULL) == 0:
            return None, True # Already running
    except:
        pass

    print("\nExpected Mosquitto not found. Starting it...")
    
    # 2. Kill any system/rogue instances first
    subprocess.run(["pkill", "mosquitto"], stderr=subprocess.DEVNULL)
    time.sleep(0.5)

    # 3. Start our instance
    try:
        p_mqtt = subprocess.Popen(
            ["mosquitto", "-c", "mosquitto.conf"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)

        if p_mqtt.poll() is not None:
            print("   ❌ Mosquitto failed to start!")
            print("   💡 Try running manually to debug: mosquitto -c mosquitto.conf -v")
            return None, False
            
        print("   ✅ Mosquitto started (ports 1883 + 9001)")
        return p_mqtt, True
        
    except FileNotFoundError:
        print("   ❌ Error: 'mosquitto' command not found. Please install it (sudo apt install mosquitto).")
        return None, False

def run_process_async(cmd_args, log_file=None, env=None):
    """Run a process in the background."""
    stdout = None
    if log_file:
        stdout = open(log_file, "w")
    
    # Use unbuffered output for python
    if cmd_args[0].endswith("python3"):
        cmd_args.insert(1, "-u")
        
    p = subprocess.Popen(
        cmd_args,
        stdout=stdout,
        stderr=subprocess.STDOUT if log_file else None,
        env=env
    )
    return p, stdout

def kill_processes(processes):
    """Kill a list of processes gracefully."""
    print("\n[CLI] Stopping all services...")
    for item in processes:
        p, f = item
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
        if f:
            f.close()

# --- Commands ---

def cmd_init(args):
    print(f"[CLI] Initializing Memory from {MANIFEST_PATH}...")
    try:
        manifest = ProjectManifest.load(MANIFEST_PATH)
        ingest_manifest(manifest)
        print("[CLI] Init Complete.")
    except Exception as e:
        print(f"[CLI] Init Failed: {e}")

def cmd_plan(args):
    query = " ".join(args.query)
    print(f"[CLI] Planning: '{query}'")

    try:
        interactive = getattr(args, 'interactive', False)
        router = ArchitectRouter(interactive=interactive)
        req = BuildRequest(
            manifest_path=MANIFEST_PATH,
            request_type="plan",
            query=query
        )
        res = router.process_request(req)
        if res.status == "SUCCESS":
            print(f"\n✅ Plan Created: {res.artifacts[0]}")
            print("Run './sage build' to execute it.")
        elif res.status == "CANCELLED":
            print(f"\n⚠️  {res.summary}")
        else:
            print(f"\n❌ Planning Failed: {res.summary}")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def cmd_build(args):
    print("[CLI] Building from Plan...")
    try:
        interactive = getattr(args, 'interactive', False)
        router = ArchitectRouter(interactive=interactive)
        req = BuildRequest(
            manifest_path=MANIFEST_PATH,
            request_type="build",
            query="BUILD_EXECUTION" 
        )
        res = router.process_request(req)
        if res.status == "SUCCESS":
            print("\n✅ Build Complete.")
        else:
            print(f"\n❌ Build Failed: {res.summary}")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def cmd_status(args):
    # Check Budget
    usage_file = ARCH_USAGE_FILE
    used = 0.0
    limit = 120.0

    if os.path.exists(usage_file):
        with open(usage_file, 'r') as f:
            data = json.load(f)
            now_key = datetime.now().strftime("%Y-%m")
            used = data.get(now_key, 0.0)

    # Check Memory
    mem_size = "Unknown"
    db_path = ".sage_memory"
    if os.path.exists(db_path):
        try:
            du = subprocess.check_output(['du','-sh', db_path]).split()[0].decode('utf-8')
            mem_size = du
        except:
            pass

    print("\n--- The Symbiote Status ---")
    print(f"💰 Monthly Budget: ${used:.2f} / ${limit:.2f}")
    print(f"🧠 Memory Size:    {mem_size}")
    print(f"📂 Manifest:       {MANIFEST_PATH}")

    # Show recent API calls if --verbose flag
    if hasattr(args, 'verbose') and args.verbose:
        log_file = ARCH_USAGE_LOG_FILE
        if os.path.exists(log_file):
            print("\n📊 Recent API Calls (last 10):")
            print("-" * 100)
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-10:]:
                    entry = json.loads(line)
                    ts = entry['timestamp'].split('T')[1][:8]  # Just time
                    print(f"  {ts} | {entry['provider']:10s} | {entry['model']:25s} | "
                          f"In: {entry['input_tokens']:6,} | Out: {entry['output_tokens']:6,} | "
                          f"${entry['cost']:.5f}")
            print("-" * 100)
        else:
            print("\n💡 Tip: Use './sage status --verbose' to see detailed API usage")

    print("---------------------------")

def cmd_update(args):
    """Research latest LLM models and update routing configuration."""
    print("🔍 Researching latest LLM models and pricing...")
    print("(This uses Sage's own routing system to research itself!)\n")

    try:
        updater = LLMUpdater()
        result = updater.update_all()

        if result["status"] == "success":
            print("\n" + "="*60)
            print("DISCOVERED MODELS")
            print("="*60)
            print(f"Total models: {result['models_found']}")
            print(f"Registry: {result['registry_path']}")

            # Show routing recommendations
            if result.get("recommendations", {}).get("routing"):
                print("\n" + "="*60)
                print("ROUTING RECOMMENDATIONS")
                print("="*60)
                routing = result["recommendations"]["routing"]
                print(json.dumps(routing, indent=2))

                print("\n" + "="*60)
                print("BUDGET ESTIMATE")
                print("="*60)
                budget = result["recommendations"].get("budget_breakdown", {})
                total = result["recommendations"].get("estimated_monthly_cost", 0)
                print(json.dumps(budget, indent=2))
                print(f"\nTotal estimated: ${total}/month")
                print(f"Your budget: $120/month")
                print(f"Safety margin: ${120 - total}/month")

                # Reasoning
                if result["recommendations"].get("reasoning"):
                    print("\n" + "="*60)
                    print("STRATEGY REASONING")
                    print("="*60)
                    print(result["recommendations"]["reasoning"])

                # Ask to apply
                print("\n" + "="*60)
                response = input("\nApply these recommendations to sage.yaml? [y/n]: ").strip().lower()
                if response == 'y':
                    updater.apply_recommendations(MANIFEST_PATH)
                    print("\n✅ Configuration updated!")
                    print("💡 Tip: Run './sage plan' to test the new routing")
                else:
                    print("\n⚠️  Recommendations saved to registry but NOT applied.")
                    print(f"   You can review: {result['registry_path']}")
            else:
                print("\n⚠️  No routing recommendations generated.")
        else:
            print(f"\n❌ Update failed: {result.get('reason', 'Unknown error')}")

    except Exception as e:
        print(f"\n❌ Update error: {e}")
        import traceback
        traceback.print_exc()

def cmd_enroll(args):
    print("🎙️ Starting Voice Enrollment...")
    subprocess.run([sys.executable, "-m", "brain.voice.enroll"])

def cmd_brain(args):
    print("🧠 Starting Sage Brain...")
    
    # Ensure MQTT is running
    p_mqtt, success = ensure_mosquitto_running()
    if not success and p_mqtt is None:
        # Failed to start, and wasn't already running
        # (If p_mqtt is None and success is True, it means it was already running)
        return

    cleanup_list = []
    if p_mqtt:
        # We started it, so we should clean it up? 
        # Actually for 'sage brain' usually we run it in FG, so yes.
        cleanup_list.append((p_mqtt, None))

    try:
        subprocess.run([sys.executable, "-u", "brain/main.py"])
    except KeyboardInterrupt:
        pass
    finally:
        kill_processes(cleanup_list)

def cmd_dashboard(args):
    print("📊 Starting Sage Dashboard...")
    subprocess.run([sys.executable, "brain/dashboard.py"])

def cmd_api(args):
    """Start Architect FastAPI backend."""
    print("🔌 Starting Architect API...")
    env = os.environ.copy()
    if getattr(args, "no_auth", False):
        env["SAGE_ARCHITECT_API_AUTH_REQUIRED"] = "false"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "architect.api.server:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if getattr(args, "reload", False):
        cmd.append("--reload")

    try:
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        pass

def cmd_lab(args):
    print("🧪 Starting Sage Voice Lab...")
    env = os.environ.copy()
    env["SAGE_LAB_HOST"] = str(args.host)
    env["SAGE_LAB_PORT"] = str(args.port)
    env["SAGE_LAB_SHARE"] = "true" if bool(args.share) else "false"
    subprocess.run([sys.executable, "-m", "brain.voice.lab"], env=env)

def cmd_voice(args):
    print("🎙️ Starting Sage Voice (Ears + Mouth)...")
    
    # Voice implies Brain usually, but here we just start voice services?
    # Voice needs MQTT too.
    p_mqtt, success = ensure_mosquitto_running()
    if not success and p_mqtt is None:
        return
        
    processes = []
    if p_mqtt:
        processes.append((p_mqtt, None))

    try:
        # Ears (STT)
        p_stt, _ = run_process_async([sys.executable, "-m", "brain.voice.transcriber"])
        processes.append((p_stt, None))
        
        # Mouth (TTS)
        if getattr(args, 'no_tts', False):
            print("   - Mouth skipped (--no-tts)")
        else:
            p_tts, _ = run_process_async([sys.executable, "-m", "brain.voice.speaker"])
            processes.append((p_tts, None))
        
        # Wait for either to exit (or KeyboardInterrupt)
        while True:
            if p_stt.poll() is not None or p_tts.poll() is not None:
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
    finally:
        kill_processes(processes)

def cmd_start(args):
    print("🚀 Starting Sage (Brain + Voice)...")
    processes = []
    
    # 1. MQTT
    p_mqtt, success = ensure_mosquitto_running()
    if not success and p_mqtt is None:
        return
    if p_mqtt:
        processes.append((p_mqtt, None))
    
    try:
        # Brain
        p_brain, _ = run_process_async([sys.executable, "-u", "brain/main.py"], log_file="/tmp/sage_brain.log")
        processes.append((p_brain, None)) # We dont hold the file handle here if we passed a path, simplistic
        print("   - Brain started (logs: /tmp/sage_brain.log)")

        # Ears (STT)
        p_stt, _ = run_process_async([sys.executable, "-m", "brain.voice.transcriber"], log_file="/tmp/sage_ears.log")
        processes.append((p_stt, None))
        print("   - Ears started (logs: /tmp/sage_ears.log)")

        # Mouth (TTS)
        if getattr(args, 'no_tts', False):
            print("   - Mouth skipped (--no-tts)")
        else:
            p_tts, _ = run_process_async([sys.executable, "-m", "brain.voice.speaker"], log_file="/tmp/sage_mouth.log")
            processes.append((p_tts, None))
            print("   - Mouth started (logs: /tmp/sage_mouth.log)")

        # Dashboard
        p_dash, _ = run_process_async([sys.executable, "brain/dashboard.py"], log_file="/tmp/sage_dashboard.log")
        processes.append((p_dash, None))
        print("   - Dashboard started (http://localhost:7860, logs: /tmp/sage_dashboard.log)")
        
        print("\n[Press Ctrl+C to stop all services]")
        
        # Monitor
        while True:
            if any(p.poll() is not None for p, _ in processes):
                print("\n[CLI] A service died unexpectedy!")
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
    finally:
        kill_processes(processes)

def cmd_pwa(args):
    """Start the complete PWA stack: MQTT + Brain + STT + TTS + API + Next.js UI"""
    print("🌐 Starting Sage PWA Stack...")
    print("=" * 60)

    processes = []
    p_stt = None
    p_tts = None
    p_api = None
    brain_env = os.environ.copy()
    cloud_override_keys = ("SAGE_FORCE_CLOUD_REASONING", "SAGE_CLOUD_PROVIDER", "SAGE_CLOUD_MODEL")

    if getattr(args, "cloud_only", False):
        brain_env["SAGE_FORCE_CLOUD_REASONING"] = "true"
        # Prevent intent-classifier Ollama fallback in cloud-only mode.
        # This keeps VRAM available for Qwen TTS.
        brain_env["INTENT_USE_LLM"] = "false"
        if getattr(args, "cloud_provider", None):
            brain_env["SAGE_CLOUD_PROVIDER"] = args.cloud_provider
        if getattr(args, "cloud_model", None):
            brain_env["SAGE_CLOUD_MODEL"] = args.cloud_model
        print(
            f"☁️  Cloud-only reasoning enabled "
            f"(provider={brain_env.get('SAGE_CLOUD_PROVIDER', 'grok')}, "
            f"model={brain_env.get('SAGE_CLOUD_MODEL', 'default')})"
        )
        print("   • INTENT_USE_LLM=false (avoid Ollama GPU usage in cloud-only mode)")
    else:
        # Ensure accidental shell exports from previous sessions don't force cloud mode.
        removed = [k for k in cloud_override_keys if k in brain_env]
        for key in cloud_override_keys:
            brain_env.pop(key, None)
        if removed:
            print("   • Cleared inherited cloud-only env overrides for local-first runtime")

    try:
        # 1. Start Mosquitto MQTT Broker
        print("\n1️⃣ Starting MQTT Broker...")
        p_mqtt, success = ensure_mosquitto_running()
        if not success and p_mqtt is None:
            return
        if p_mqtt:
            processes.append((p_mqtt, None))

        # 2. Start Brain (optional, with STT/TTS disabled by default)
        if not args.no_brain:
            print("\n2️⃣ Starting Brain Core...")
            brain_log_path = None if args.brain_logs else "/tmp/sage_brain.log"
            p_brain, _ = run_process_async(
                [sys.executable, "-u", "brain/main.py"],
                log_file=brain_log_path,
                env=brain_env
            )
            processes.append((p_brain, None))
            if args.brain_logs:
                print("   ✅ Brain started (logs: console)")
            else:
                print("   ✅ Brain started (logs: /tmp/sage_brain.log)")
        else:
            print("\n2️⃣ Skipping Brain (--no-brain flag)")

        # 2b. Start STT service for PWA voice mode
        if not args.no_stt:
            print("\n2️⃣ Starting STT Service...")
            p_stt, _ = run_process_async(
                [sys.executable, "-m", "brain.voice.transcriber"],
                log_file="/tmp/sage_stt.log"
            )
            processes.append((p_stt, None))
            print("   ✅ STT started (logs: /tmp/sage_stt.log)")
        else:
            print("\n2️⃣ Skipping STT (--no-stt flag)")

        # 2c. Start TTS speaker service for PWA voice mode
        if not args.no_tts:
            print("\n2️⃣ Starting TTS Service...")
            p_tts, _ = run_process_async(
                [sys.executable, "-m", "brain.voice.speaker"],
                log_file="/tmp/sage_tts.log"
            )
            processes.append((p_tts, None))
            print("   ✅ TTS started (logs: /tmp/sage_tts.log)")
        else:
            print("\n2️⃣ Skipping TTS (--no-tts flag)")

        # 2d. Start Architect API backend
        if not args.no_api:
            print("\n2️⃣ Starting Architect API...")
            api_env = os.environ.copy()
            if args.api_no_auth:
                api_env["SAGE_ARCHITECT_API_AUTH_REQUIRED"] = "false"
            api_log_path = None if args.api_logs else "/tmp/sage_architect_api.log"
            api_cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                "architect.api.server:app",
                "--host",
                args.api_host,
                "--port",
                str(args.api_port),
            ]
            if args.api_reload:
                api_cmd.append("--reload")

            p_api, _ = run_process_async(
                api_cmd,
                log_file=api_log_path,
                env=api_env,
            )
            processes.append((p_api, None))
            if args.api_logs:
                print("   ✅ Architect API started (logs: console)")
            else:
                print("   ✅ Architect API started (logs: /tmp/sage_architect_api.log)")
        else:
            print("\n2️⃣ Skipping Architect API (--no-api flag)")

        # 3. Start Next.js PWA UI
        print("\n3️⃣ Starting PWA UI...")

        # Check if .env.local exists
        env_path = ARCH_UI_ENV_LOCAL
        if not os.path.exists(env_path):
            print("   Creating .env.local from example...")
            subprocess.run([
                "cp",
                ARCH_UI_ENV_EXAMPLE,
                env_path
            ])

        # Get network IP for display
        try:
            network_ip = subprocess.check_output(
                ["hostname", "-I"],
                stderr=subprocess.DEVNULL
            ).decode().split()[0]
        except:
            network_ip = "localhost"

        # Start Next.js
        npm_cmd = ["npm", "run", "dev:network"]
        p_nextjs = subprocess.Popen(
            npm_cmd,
            cwd=ARCH_UI_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append((p_nextjs, None))

        # Wait for Next.js to be ready
        print("   Starting Next.js server...")
        ready = False
        for i in range(30):  # 30 second timeout
            if p_nextjs.poll() is not None:
                print("   ❌ Next.js failed to start!")
                print(f"   💡 Check: cd {ARCH_UI_DIR} && npm run dev:network")
                return

            # Check if port 3000 is listening
            try:
                result = subprocess.run(
                    ["netstat", "-tuln"],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if ":3000" in result.stdout:
                    ready = True
                    break
            except:
                pass

            time.sleep(1)

        if not ready:
            print("   ⚠️  Next.js may still be starting...")
        else:
            print("   ✅ Next.js running (port 3000)")

        # Display access information
        print("\n" + "=" * 60)
        print("🎉 Sage PWA is READY!")
        print("=" * 60)
        print("\n📱 Access Points:")
        print(f"   Desktop:  http://localhost:3000/brain")
        print(f"   Network:  http://{network_ip}:3000/brain")
        if not args.no_api:
            print(f"   API:      http://localhost:{args.api_port}")
            print(f"   API LAN:  http://{network_ip}:{args.api_port}")

        if args.no_brain:
            print("\n⚠️  Brain not running - UI will show 'offline' status")
            print("   Start brain separately: ./sage brain")

        print("\n🔧 Services Running:")
        print("   • MQTT Broker:  ✅ (1883 + 9001)")
        if not args.no_brain:
            print("   • Brain Core:   ✅ (see /tmp/sage_brain.log)")
        if not args.no_stt:
            print("   • STT Service:  ✅ (see /tmp/sage_stt.log)")
        if not args.no_tts:
            print("   • TTS Service:  ✅ (see /tmp/sage_tts.log)")
        if not args.no_api:
            if args.api_logs:
                print("   • Architect API: ✅ (logs: console)")
            else:
                print("   • Architect API: ✅ (see /tmp/sage_architect_api.log)")
        print("   • Next.js PWA:  ✅ (port 3000)")

        print("\n💡 Features:")
        print("   • Real-time brain monitoring")
        print("   • STT/TTS toggle controls")
        print("   • Live chat interface")
        print("   • Mobile-friendly (PWA)")

        print("\n🛑 To stop: Press Ctrl+C")
        print("=" * 60 + "\n")

        # Monitor processes
        brain_reported_down = False
        api_reported_down = False
        while True:
            # Check if any critical process died
            if p_mqtt and p_mqtt.poll() is not None:
                print("\n❌ MQTT broker stopped unexpectedly!")
                break
            if p_nextjs.poll() is not None:
                print("\n❌ Next.js stopped unexpectedly!")
                break
            if not args.no_brain and p_brain.poll() is not None:
                if not brain_reported_down:
                    code = p_brain.returncode
                    print(f"\n⚠️  Brain stopped (exit code: {code})")
                    if not args.brain_logs:
                        print("   Check logs: /tmp/sage_brain.log")
                    print("   UI will continue running; restart Brain with: ./sage brain")
                    brain_reported_down = True
            if not args.no_api and p_api and p_api.poll() is not None:
                if not api_reported_down:
                    code = p_api.returncode
                    print(f"\n⚠️  Architect API stopped (exit code: {code})")
                    if not args.api_logs:
                        print("   Check logs: /tmp/sage_architect_api.log")
                    print("   UI will continue running; restart API with: ./sage api")
                    api_reported_down = True
            if not args.no_stt and p_stt and p_stt.poll() is not None:
                code = p_stt.returncode
                print(f"\n⚠️  STT service stopped (exit code: {code})")
                print("   Check logs: /tmp/sage_stt.log")
                print("   UI will continue running; restart STT with: python -m brain.voice.transcriber")
                p_stt = None
            if not args.no_tts and p_tts and p_tts.poll() is not None:
                code = p_tts.returncode
                print(f"\n⚠️  TTS service stopped (exit code: {code})")
                print("   Check logs: /tmp/sage_tts.log")
                print("   UI will continue running; restart TTS with: python -m brain.voice.speaker")
                p_tts = None

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down Sage PWA...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        kill_processes(processes)
        subprocess.run(["pkill", "mosquitto"], stderr=subprocess.DEVNULL)
        print("\n✅ All services stopped.")

def cmd_vision(args):
    """Start the hybrid vision pipeline with face detection, YOLO, and optional VLM."""
    print("👁️  Starting Sage Vision Pipeline...")
    print("=" * 60)

    # Build command arguments (without python executable)
    cmd_args = ["brain/vision/hybrid_pipeline.py"]

    # Feature flags
    if args.no_vlm:
        cmd_args.append("--no-vlm")
        print("   VLM: disabled")
    else:
        print(f"   VLM: {args.vlm_model} (every {args.vlm_interval}s)")
        cmd_args.extend(["--vlm-model", args.vlm_model])
        cmd_args.extend(["--vlm-interval", str(args.vlm_interval)])

    if args.no_emotion:
        cmd_args.append("--no-emotion")
        print("   Emotion: disabled")
    else:
        print("   Emotion: enabled (DeepFace)")

    if args.no_yolo:
        cmd_args.append("--no-yolo")
        print("   YOLO: disabled")
    else:
        print(f"   YOLO: {args.yolo_model} (every {args.yolo_interval} frames)")
        cmd_args.extend(["--yolo-model", args.yolo_model])
        cmd_args.extend(["--yolo-interval", str(args.yolo_interval)])

    if args.no_ui:
        cmd_args.append("--no-ui")
        print("   UI: disabled")
    else:
        print("   UI: enabled (press 'q' to quit, 'v' for VLM)")

    print("=" * 60)
    print("\n🎥 Starting camera...")

    # Check for vision venv
    venv_python = ".venv-vision/bin/python3"
    if os.path.exists(venv_python):
        # Use vision venv's Python directly
        cmd = [venv_python] + cmd_args
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n\n👁️  Vision pipeline stopped.")
    else:
        # Fall back to current venv
        print("   ⚠️  .venv-vision not found, using current environment")
        print("   💡 Create it: python3 -m venv .venv-vision && source .venv-vision/bin/activate")
        print("      pip install opencv-python insightface onnxruntime-gpu deepface ultralytics paho-mqtt")
        cmd = [sys.executable] + cmd_args
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n\n👁️  Vision pipeline stopped.")


def cmd_collect(args):
    """Launch the Sheng data collection UI for training."""
    print("🎙️ Sheng Data Collection")

    if args.export:
        from brain.voice.data_collector import export_training_data
        result = export_training_data()
        print(result)
    else:
        subprocess.run([sys.executable, "-m", "brain.voice.data_collector"])

def cmd_train(args):
    """Run training pipeline steps."""
    subcmd = args.train_command

    if subcmd == "setup":
        print("⚙️ Setting up training environment...")
        subprocess.run(["bash", "brain/voice/training/setup_training.sh"])

    elif subcmd == "prepare-tts":
        print("📦 Preparing TTS training data...")
        cmd = [sys.executable, "brain/voice/training/prepare_tts_data.py"]
        if args.device:
            cmd.extend(["--device", args.device])
        subprocess.run(cmd)

    elif subcmd == "tts":
        print(f"🔧 Fine-tuning Qwen3-TTS ({args.size})...")
        cmd = [sys.executable, "brain/voice/training/finetune_tts.py",
               "--size", args.size, "--epochs", str(args.epochs),
               "--batch-size", str(args.batch_size),
               "--lr", str(args.lr),
               "--speaker-name", args.speaker_name]
        subprocess.run(cmd)

    elif subcmd == "prepare-stt":
        print("📦 Preparing STT training data...")
        cmd = [sys.executable, "brain/voice/training/prepare_stt_data.py"]
        if args.augment_swahili:
            cmd.append("--augment-swahili")
        subprocess.run(cmd)

    elif subcmd == "stt":
        print(f"🔧 Fine-tuning Whisper ({args.whisper_model})...")
        cmd = [sys.executable, "brain/voice/training/finetune_stt.py",
               "--model", args.whisper_model, "--epochs", str(args.epochs)]
        if args.data_dir:
            cmd.extend(["--data-dir", args.data_dir])
        subprocess.run(cmd)

    elif subcmd == "export-stt":
        print("📤 Exporting fine-tuned Whisper to CTranslate2...")
        cmd = [sys.executable, "brain/voice/training/export_stt.py",
               "--model", args.whisper_model]
        subprocess.run(cmd)

    elif subcmd == "prepare-feedback":
        print(f"🧪 Preparing feedback dataset ({args.task})...")
        cmd = [sys.executable, "brain/voice/training/prepare_feedback_data.py", "--task", args.task]
        if args.feedback_jsonl:
            cmd.extend(["--feedback-jsonl", args.feedback_jsonl])
        if args.output_dir:
            cmd.extend(["--output-dir", args.output_dir])
        cmd.extend(["--val-split", str(args.val_split)])
        if args.include_base:
            cmd.append("--include-base")
        if args.base_dataset_dir:
            cmd.extend(["--base-dataset-dir", args.base_dataset_dir])
        if args.only_marked:
            cmd.append("--only-marked")
        else:
            cmd.append("--include-unmarked")
        cmd.extend(["--min-quality", str(args.min_quality)])
        cmd.extend(["--max-repeats", str(args.max_repeats)])
        cmd.extend(["--seed", str(args.seed)])
        subprocess.run(cmd)

    elif subcmd == "eval":
        print(f"🎧 Evaluating TTS quality ({args.size})...")
        cmd = [sys.executable, "brain/voice/training/eval_tts.py", "--size", args.size]
        if args.checkpoint is not None:
            cmd.extend(["--checkpoint", str(args.checkpoint)])
        subprocess.run(cmd)

    else:
        print(f"Unknown train command: {subcmd}")
        print("Available: setup, prepare-tts, tts, prepare-stt, stt, export-stt, prepare-feedback, eval")

def cmd_switches(args):
    """
    Minimal voice loop: STT -> switch controller -> Zigbee panel (or simulator) -> TTS.
    No brain, no LLM, no architect. See docs/VOICE_SWITCH_BASICS.md.
    """
    print("🔀 Starting Sage voice switches (STT + switch controller + TTS)...")

    if getattr(args, "say", None):
        subprocess.run([sys.executable, "-m", "brain.devices.switch_controller", "--say", args.say])
        return
    if getattr(args, "discover", False):
        subprocess.run([sys.executable, "-m", "brain.devices.switch_controller", "--discover"])
        return

    p_mqtt, success = ensure_mosquitto_running()
    if not success and p_mqtt is None:
        return

    processes = []
    if p_mqtt:
        processes.append((p_mqtt, None))

    try:
        if getattr(args, "sim", False):
            p_node, _ = run_process_async([sys.executable, "-m", "brain.devices.switch_node", "--backend", "sim"])
            processes.append((p_node, None))
            print("   - Simulated switch panel started (no hardware; prints ON/OFF)")
        else:
            print("   - Real switches: expecting Zigbee2MQTT on this broker (use --sim to fake the panel)")

        p_ctl, _ = run_process_async([sys.executable, "-m", "brain.devices.switch_controller"])
        processes.append((p_ctl, None))
        print("   - Switch controller started (listens on sage/voice/transcript)")

        if getattr(args, "no_stt", False):
            print("   - Ears skipped (--no-stt); inject text with: ./sage switches --say 'lamp on'")
        else:
            p_stt, _ = run_process_async([sys.executable, "-m", "brain.voice.transcriber"])
            processes.append((p_stt, None))
            print("   - Ears started (STT)")

        if getattr(args, "no_tts", False):
            print("   - Mouth skipped (--no-tts)")
        else:
            p_tts, _ = run_process_async([sys.executable, "-m", "brain.voice.speaker"])
            processes.append((p_tts, None))
            print("   - Mouth started (TTS)")

        print("\n[Press Ctrl+C to stop all services]")
        while True:
            if any(p.poll() is not None for p, _ in processes):
                print("\n[CLI] A service died unexpectedly!")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        kill_processes(processes)

def cmd_stop(args):
    print("🛑 Stopping Sage Services...")
    patterns = [
        "brain/main.py",
        "brain/dashboard.py",
        "architect.api.server:app",
        "brain.voice.transcriber",
        "brain.voice.speaker",
        "brain.devices.switch_controller",
        "brain.devices.switch_node",
        "hybrid_pipeline.py",
        "vision_service.py",
        "mosquitto",
    ]

    for p in patterns:
        subprocess.run(["pkill", "-f", p], stderr=subprocess.DEVNULL)

    # Also stop Next.js (more specific)
    subprocess.run(["pkill", "-f", "next"], stderr=subprocess.DEVNULL)

    print("✅ Sage stopped.")

def main():
    parser = argparse.ArgumentParser(description="Sage Symbiote CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Architect Commands
    subparsers.add_parser("init", help="Initialize codebase memory").set_defaults(func=cmd_init)

    parser_plan = subparsers.add_parser("plan", help="Draft an implementation plan")
    parser_plan.add_argument("query", nargs="+", help="What to build")
    parser_plan.add_argument("-i", "--interactive", action="store_true", help="Interactive mode (prompt for approval)")
    parser_plan.set_defaults(func=cmd_plan)

    parser_build = subparsers.add_parser("build", help="Execute the current plan")
    parser_build.add_argument("-i", "--interactive", action="store_true", help="Interactive mode (prompt for approval)")
    parser_build.set_defaults(func=cmd_build)

    subparsers.add_parser("update", help="Research latest LLM models and update routing").set_defaults(func=cmd_update)

    parser_status = subparsers.add_parser("status", help="Show system status")
    parser_status.add_argument("-v", "--verbose", action="store_true", help="Show detailed API usage logs")
    parser_status.set_defaults(func=cmd_status)

    subparsers.add_parser("stop", help="Stop all Sage services").set_defaults(func=cmd_stop)

    # Setup Commands
    subparsers.add_parser("enroll", help="Record your voice").set_defaults(func=cmd_enroll)

    # Data Collection
    parser_collect = subparsers.add_parser("collect", help="Record Sheng training data")
    parser_collect.add_argument("--export", action="store_true", help="Export collected data to training format")
    parser_collect.set_defaults(func=cmd_collect)

    # Training Commands
    parser_train = subparsers.add_parser("train", help="Training pipeline (TTS/STT)")
    train_sub = parser_train.add_subparsers(dest="train_command")

    train_sub.add_parser("setup", help="Setup training environment & download models")
    train_sub.add_parser("prepare-tts", help="Prepare data for TTS fine-tuning")
    parser_train_tts = train_sub.add_parser("tts", help="Fine-tune Qwen3-TTS")
    parser_train_tts.add_argument("--size", choices=["0.6b", "1.7b"], default="0.6b")
    parser_train_tts.add_argument("--epochs", type=int, default=3)
    parser_train_tts.add_argument("--batch-size", type=int, default=2)
    parser_train_tts.add_argument("--lr", type=float, default=2e-5)
    parser_train_tts.add_argument("--speaker-name", default="sage_sheng")

    parser_train_stt_prep = train_sub.add_parser("prepare-stt", help="Prepare data for STT fine-tuning")
    parser_train_stt_prep.add_argument("--augment-swahili", action="store_true")

    parser_train_stt = train_sub.add_parser("stt", help="Fine-tune Whisper for Sheng")
    parser_train_stt.add_argument("--whisper-model", default="whisper-small")
    parser_train_stt.add_argument("--epochs", type=int, default=3)
    parser_train_stt.add_argument("--data-dir", default=None, help="Override STT dataset directory")

    parser_export_stt = train_sub.add_parser("export-stt", help="Export Whisper to CTranslate2")
    parser_export_stt.add_argument("--whisper-model", default="whisper-small")

    parser_feedback = train_sub.add_parser("prepare-feedback", help="Prepare retraining dataset from lab annotations")
    parser_feedback.add_argument("--task", choices=["stt"], default="stt")
    parser_feedback.add_argument("--feedback-jsonl", default=None)
    parser_feedback.add_argument("--output-dir", default=None)
    parser_feedback.add_argument("--val-split", type=float, default=0.1)
    parser_feedback.add_argument("--include-base", action="store_true")
    parser_feedback.add_argument("--base-dataset-dir", default=None)
    parser_feedback.add_argument("--only-marked", dest="only_marked", action="store_true")
    parser_feedback.add_argument("--include-unmarked", dest="only_marked", action="store_false")
    parser_feedback.add_argument("--min-quality", type=int, default=1)
    parser_feedback.add_argument("--max-repeats", type=int, default=3)
    parser_feedback.add_argument("--seed", type=int, default=42)
    parser_feedback.set_defaults(only_marked=True)

    parser_eval = train_sub.add_parser("eval", help="Evaluate fine-tuned TTS quality")
    parser_eval.add_argument("--size", choices=["0.6b", "1.7b"], default="0.6b")
    parser_eval.add_argument("--checkpoint", type=int, default=None,
                             help="Specific epoch checkpoint to eval (e.g. 0, 1, 2)")

    # Set defaults for train subcommands
    parser_train.set_defaults(func=cmd_train, device="cuda", size="0.6b",
                              whisper_model="whisper-small", epochs=3,
                              batch_size=2, lr=2e-5, speaker_name="sage_sheng",
                              augment_swahili=False)

    # Runtime Commands
    subparsers.add_parser("brain", help="Start the Brain").set_defaults(func=cmd_brain)
    parser_api = subparsers.add_parser("api", help="Start Architect API backend")
    parser_api.add_argument("--host", default="0.0.0.0", help="API bind host (default: 0.0.0.0)")
    parser_api.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")
    parser_api.add_argument("--reload", action="store_true", help="Enable uvicorn reload mode")
    parser_api.add_argument("--no-auth", action="store_true", help="Disable API token auth for local dev")
    parser_api.set_defaults(func=cmd_api)
    subparsers.add_parser("dashboard", help="Start the Dashboard").set_defaults(func=cmd_dashboard)
    subparsers.add_parser("ui", help="Alias for dashboard").set_defaults(func=cmd_dashboard)
    parser_lab = subparsers.add_parser("lab", help="Start the Voice Lab")
    parser_lab.add_argument("--host", default="127.0.0.1", help="Bind host (use 127.0.0.1 for browser mic)")
    parser_lab.add_argument("--port", type=int, default=7860, help="Voice Lab port")
    parser_lab.add_argument("--share", action="store_true", help="Create HTTPS Gradio share URL (for remote mic use)")
    parser_lab.set_defaults(func=cmd_lab)
    
    parser_voice = subparsers.add_parser("voice", help="Start Voice Services (STT+TTS)")
    parser_voice.add_argument("--no-tts", action="store_true", help="Disable TTS (Mouth)")
    parser_voice.set_defaults(func=cmd_voice)

    parser_switches = subparsers.add_parser("switches", help="Minimal voice loop: STT + switch controller + TTS (no brain)")
    parser_switches.add_argument("--sim", action="store_true", help="Run a simulated switch panel instead of Zigbee2MQTT")
    parser_switches.add_argument("--no-stt", action="store_true", help="Do not start STT (use --say to inject text)")
    parser_switches.add_argument("--no-tts", action="store_true", help="Do not start TTS")
    parser_switches.add_argument("--say", metavar="TEXT", help="Inject TEXT as a transcript into a running loop and exit")
    parser_switches.add_argument("--discover", action="store_true", help="List Zigbee2MQTT devices and their switch keys")
    parser_switches.set_defaults(func=cmd_switches)

    parser_start = subparsers.add_parser("start", help="Start Everything (Brain+Voice)")
    parser_start.add_argument("--no-tts", action="store_true", help="Disable TTS (Mouth)")
    parser_start.set_defaults(func=cmd_start)

    # PWA Command
    parser_pwa = subparsers.add_parser("pwa", help="Start PWA Stack (MQTT + Brain + STT + TTS + API + UI)")
    parser_pwa.add_argument("--no-brain", action="store_true", help="Start only MQTT and UI (no brain)")
    parser_pwa.add_argument("--no-stt", action="store_true", help="Do not start STT transcriber service")
    parser_pwa.add_argument("--no-tts", action="store_true", help="Do not start TTS speaker service")
    parser_pwa.add_argument("--no-api", action="store_true", help="Do not start Architect API service")
    parser_pwa.add_argument("--api-host", default="0.0.0.0", help="Architect API bind host")
    parser_pwa.add_argument("--api-port", type=int, default=8000, help="Architect API port")
    parser_pwa.add_argument("--api-reload", action="store_true", help="Start Architect API with --reload")
    parser_pwa.add_argument("--api-logs", action="store_true", help="Stream API logs to console")
    parser_pwa.add_argument("--api-no-auth", action="store_true", help="Disable API auth for local dev")
    parser_pwa.add_argument(
        "--cloud-only",
        action="store_true",
        help="Force Brain reasoning to use cloud LLM only (skip local Ollama)"
    )
    parser_pwa.add_argument(
        "--cloud-provider",
        choices=["grok", "openai"],
        default="grok",
        help="Cloud provider used with --cloud-only (default: grok)"
    )
    parser_pwa.add_argument(
        "--cloud-model",
        default=None,
        help="Optional cloud model override for --cloud-only (e.g., gpt-4o-mini)"
    )
    parser_pwa.add_argument(
        "--brain-logs",
        action="store_true",
        help="Stream Brain logs to console (like './sage brain')"
    )
    parser_pwa.set_defaults(func=cmd_pwa)

    # Vision Command
    parser_vision = subparsers.add_parser("vision", help="Start Vision Pipeline (Face + YOLO + VLM)")
    parser_vision.add_argument("--no-vlm", action="store_true", help="Disable VLM scene description")
    parser_vision.add_argument("--no-emotion", action="store_true", help="Disable emotion detection")
    parser_vision.add_argument("--no-yolo", action="store_true", help="Disable YOLO object detection")
    parser_vision.add_argument("--no-ui", action="store_true", help="Run without UI window")
    parser_vision.add_argument("--vlm-model", type=str, default="moondream", help="VLM model (default: moondream)")
    parser_vision.add_argument("--vlm-interval", type=float, default=60, help="VLM trigger interval in seconds")
    parser_vision.add_argument("--yolo-model", type=str, default="yolov8n", help="YOLO model (yolov8n/s/m)")
    parser_vision.add_argument("--yolo-interval", type=int, default=5, help="Run YOLO every N frames")
    parser_vision.set_defaults(func=cmd_vision)

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
