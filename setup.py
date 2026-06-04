"""
Jarvis Setup Wizard
-------------------
Run this once after cloning the repo. It will:
  1. Create a virtual environment and install dependencies
  2. Check / download Ollama and the LLM model
  3. Download the Kokoro TTS model files
  4. Detect your hardware and set Whisper settings
  5. Detect your microphone
  6. Set a wake word
  7. Authenticate with Google (Gmail + Calendar)
  8. Write your .env file

Usage:
  python setup.py
"""

import os
import sys
import platform
import subprocess
import shutil
import urllib.request
import json
from pathlib import Path

REPO_ROOT  = Path(__file__).parent
ENV_FILE   = REPO_ROOT / ".env"
IS_WINDOWS = platform.system() == "Windows"
IS_MAC     = platform.system() == "Darwin"

# ── Helpers ───────────────────────────────────────────────────────────────────

def title(text: str):
    print(f"\n{'='*54}")
    print(f"  {text}")
    print(f"{'='*54}")


def step(text: str):
    print(f"\n▶  {text}")


def ok(text: str):
    print(f"   ✓  {text}")


def warn(text: str):
    print(f"   ⚠  {text}")


def ask(prompt: str, default: str = "") -> str:
    if default:
        val = input(f"   {prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"   {prompt}: ").strip()


def confirm(prompt: str) -> bool:
    return ask(f"{prompt} (y/n)", "y").lower().startswith("y")


def run(cmd, check=True, capture=False, **kwargs):
    return subprocess.run(
        cmd, check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        **kwargs
    )


# ── Step 1: Virtual environment ───────────────────────────────────────────────

def setup_venv() -> Path:
    title("Step 1 — Virtual environment")

    venv_path = REPO_ROOT / ".venv"

    if venv_path.exists():
        ok(f"Virtual environment already exists at {venv_path}")
    else:
        step("Creating virtual environment...")
        run([sys.executable, "-m", "venv", str(venv_path)])
        ok("Virtual environment created")

    # Return path to pip inside the venv
    if IS_WINDOWS:
        pip = venv_path / "Scripts" / "pip.exe"
        python = venv_path / "Scripts" / "python.exe"
    else:
        pip = venv_path / "bin" / "pip"
        python = venv_path / "bin" / "python"

    step("Installing dependencies (this may take a few minutes)...")
    run([str(pip), "install", "--upgrade", "pip", "-q"])
    run([str(pip), "install", "-r", str(REPO_ROOT / "requirements.txt"), "-q"])
    ok("All dependencies installed")

    return python


# ── Step 2: Ollama ────────────────────────────────────────────────────────────

def setup_ollama(env: dict):
    title("Step 2 — Ollama & LLM model")

    if shutil.which("ollama") is None:
        warn("Ollama not found.")
        print("\n   Please install Ollama from https://ollama.com/download")
        print("   After installing, re-run this setup script.")
        if confirm("   Open the Ollama download page now?"):
            import webbrowser
            webbrowser.open("https://ollama.com/download")
        sys.exit(0)
    else:
        ok("Ollama is installed")

    # Check if ollama is running
    try:
        result = run(["ollama", "list"], capture=True, check=False)
        output = result.stdout.decode() if result.stdout else ""
    except Exception:
        output = ""

    # Pick model
    default_model = "qwen3:8b"
    print(f"\n   Recommended model: {default_model} (fast, good tool-calling)")
    print("   Alternatives: llama3.1:8b, mistral:7b, phi4:latest")
    model = ask("Which Ollama model do you want to use?", default_model)

    if model.lower() in output.lower():
        ok(f"{model} is already downloaded")
    else:
        step(f"Pulling {model} (this may take several minutes)...")
        run(["ollama", "pull", model])
        ok(f"{model} downloaded")

    env["OLLAMA_MODEL"] = model
    env["OLLAMA_BASE_URL"] = "http://localhost:11434"


# ── Step 3: Kokoro TTS model files ────────────────────────────────────────────

def setup_kokoro():
    title("Step 3 — Kokoro TTS model files")

    base_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

    # Pick right model for platform
    if IS_WINDOWS:
        model_file = "kokoro-v1.0.fp16-gpu.onnx"
        model_desc = "Windows GPU (fp16)"
    else:
        model_file = "kokoro-v1.0.fp16.onnx"
        model_desc = "Mac/Linux CPU (fp16)"

    model_path  = REPO_ROOT / model_file
    voices_path = REPO_ROOT / "voices-v1.0.bin"

    if model_path.exists():
        ok(f"Model file already exists: {model_file}")
    else:
        step(f"Downloading Kokoro model ({model_desc})...")
        _download(f"{base_url}/{model_file}", model_path)
        ok(f"Downloaded {model_file}")

    if voices_path.exists():
        ok("Voices file already exists")
    else:
        step("Downloading voices file...")
        _download(f"{base_url}/voices-v1.0.bin", voices_path)
        ok("Downloaded voices-v1.0.bin")


def _download(url: str, dest: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r   {pct:.1f}% ({downloaded // 1_000_000}MB / {total // 1_000_000}MB)", end="", flush=True)
    print()


# ── Step 4: Hardware detection ────────────────────────────────────────────────

def setup_hardware(env: dict):
    title("Step 4 — Hardware detection")

    system = platform.system()
    whisper_device      = "cpu"
    whisper_compute     = "int8"

    if system == "Windows":
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                ok(f"NVIDIA GPU detected: {gpu_name}")
                whisper_device  = "cuda"
                whisper_compute = "float16"
            else:
                warn("No CUDA GPU detected — using CPU")
        except ImportError:
            warn("PyTorch not available yet — defaulting to CPU")

    elif system == "Darwin":
        chip = platform.processor()
        if "arm" in chip.lower() or _is_apple_silicon():
            ok("Apple Silicon detected — using optimised CPU int8")
        else:
            ok("Intel Mac detected — using CPU int8")
        whisper_device  = "cpu"
        whisper_compute = "int8"

    else:  # Linux
        try:
            import torch
            if torch.cuda.is_available():
                ok(f"NVIDIA GPU detected")
                whisper_device  = "cuda"
                whisper_compute = "float16"
            else:
                warn("No CUDA GPU — using CPU")
        except ImportError:
            warn("PyTorch not available yet — defaulting to CPU")

    ok(f"Whisper will run on: {whisper_device} / {whisper_compute}")
    env["WHISPER_DEVICE"]       = whisper_device
    env["WHISPER_COMPUTE_TYPE"] = whisper_compute
    env["WHISPER_MODEL"]        = "large-v3-turbo"
    env["WHISPER_LANGUAGE"]     = ask("What language will you mostly speak?", "en")


def _is_apple_silicon() -> bool:
    try:
        result = run(["sysctl", "-n", "machdep.cpu.brand_string"],
                     capture=True, check=False)
        return "Apple" in (result.stdout.decode() if result.stdout else "")
    except Exception:
        return False


# ── Step 5: Microphone ────────────────────────────────────────────────────────

def setup_microphone(env: dict):
    title("Step 5 — Microphone")

    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [(i, d) for i, d in enumerate(devices)
                      if d['max_input_channels'] > 0
                      and 'stereo mix' not in d['name'].lower()
                      and 'loopback' not in d['name'].lower()]

        if not input_devs:
            warn("No input devices found.")
            env["AUDIO_DEVICE_NAME"] = ""
            return

        print("\n   Available microphones:")
        for i, (idx, d) in enumerate(input_devs):
            print(f"   {i+1}. {d['name']}")

        if len(input_devs) == 1:
            ok(f"Only one mic found: {input_devs[0][1]['name']}")
            env["AUDIO_DEVICE_NAME"] = ""
        else:
            choice = ask("Which mic do you want to use? (number, or press Enter to auto-detect)", "")
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(input_devs):
                    env["AUDIO_DEVICE_NAME"] = input_devs[idx][1]['name'][:30]
                    ok(f"Selected: {env['AUDIO_DEVICE_NAME']}")
                else:
                    env["AUDIO_DEVICE_NAME"] = ""
            else:
                env["AUDIO_DEVICE_NAME"] = ""
                ok("Will auto-detect microphone on startup")

    except Exception as e:
        warn(f"Could not list audio devices: {e}")
        env["AUDIO_DEVICE_NAME"] = ""


# ── Step 6: Wake word ─────────────────────────────────────────────────────────

def setup_wake_word(env: dict):
    title("Step 6 — Wake word")

    print("\n   A wake word means Jarvis only listens after you say a trigger word.")
    print("   Example: say 'Jarvis' then ask your question.")
    print("   Leave blank to have Jarvis always listening.")

    wake_word = ask("Wake word (e.g. 'jarvis', or press Enter to skip)", "jarvis")
    env["WAKE_WORD"] = wake_word

    if wake_word:
        ok(f"Wake word set to: '{wake_word}'")
    else:
        ok("Always-listening mode enabled")

    env["KOKORO_VOICE"] = ask("TTS voice (press Enter for default)", "am_michael")


# ── Step 7: Google OAuth ──────────────────────────────────────────────────────

def setup_google():
    title("Step 7 — Google Authentication (Gmail & Calendar)")

    creds_path = REPO_ROOT / "credentials.json"

    if not creds_path.exists():
        print("""
   To connect Gmail and Google Calendar, you need a Google OAuth credentials file.

   Steps:
   1. Go to https://console.cloud.google.com
   2. Create a new project (name it 'Jarvis')
   3. Go to 'APIs & Services' → 'Enable APIs'
      - Enable 'Gmail API'
      - Enable 'Google Calendar API'
   4. Go to 'APIs & Services' → 'OAuth consent screen'
      - Choose 'External', fill in app name 'Jarvis'
      - Add your Gmail as a test user
      - Add scopes: gmail.readonly, calendar.readonly
   5. Go to 'APIs & Services' → 'Credentials'
      - Create credentials → OAuth 2.0 Client ID
      - Application type: Desktop app
      - Download the JSON and save it as 'credentials.json' in this folder
""")
        if confirm("   Open Google Cloud Console now?"):
            import webbrowser
            webbrowser.open("https://console.cloud.google.com")

        input("\n   Press Enter once you've saved credentials.json to this folder...")

        if not creds_path.exists():
            warn("credentials.json still not found — skipping Google auth.")
            warn("You can run this setup again later, or add credentials.json manually.")
            return

    ok("credentials.json found")

    # Authenticate Gmail
    step("Authenticating with Gmail (browser will open)...")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials

        gmail_token = REPO_ROOT / "token_gmail.json"
        if not gmail_token.exists():
            flow  = InstalledAppFlow.from_client_secrets_file(
                str(creds_path),
                ["https://www.googleapis.com/auth/gmail.readonly"]
            )
            creds = flow.run_local_server(port=0)
            with open(gmail_token, "w") as f:
                f.write(creds.to_json())
            ok("Gmail authenticated")
        else:
            ok("Gmail already authenticated")

        # Authenticate Calendar
        step("Authenticating with Google Calendar (browser will open)...")
        cal_token = REPO_ROOT / "token_calendar.json"
        if not cal_token.exists():
            flow  = InstalledAppFlow.from_client_secrets_file(
                str(creds_path),
                ["https://www.googleapis.com/auth/calendar.readonly"]
            )
            creds = flow.run_local_server(port=0)
            with open(cal_token, "w") as f:
                f.write(creds.to_json())
            ok("Google Calendar authenticated")
        else:
            ok("Google Calendar already authenticated")

    except Exception as e:
        warn(f"Google auth failed: {e}")
        warn("You can re-run setup.py later to authenticate.")


# ── Step 8: Write .env ────────────────────────────────────────────────────────

def write_env(env: dict):
    title("Step 8 — Writing .env")

    # Preserve any existing values not set by setup
    existing = {}
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()

    existing.update(env)  # setup values override

    lines = [
        "# Jarvis configuration — generated by setup.py\n",
        f"OLLAMA_MODEL={existing.get('OLLAMA_MODEL', 'qwen3:8b')}",
        f"OLLAMA_BASE_URL={existing.get('OLLAMA_BASE_URL', 'http://localhost:11434')}",
        f"WHISPER_MODEL={existing.get('WHISPER_MODEL', 'large-v3-turbo')}",
        f"WHISPER_LANGUAGE={existing.get('WHISPER_LANGUAGE', 'en')}",
        f"WHISPER_DEVICE={existing.get('WHISPER_DEVICE', 'cpu')}",
        f"WHISPER_COMPUTE_TYPE={existing.get('WHISPER_COMPUTE_TYPE', 'int8')}",
        f"KOKORO_VOICE={existing.get('KOKORO_VOICE', 'am_michael')}",
        f"AUDIO_DEVICE_NAME={existing.get('AUDIO_DEVICE_NAME', '')}",
        f"VAD_THRESHOLD={existing.get('VAD_THRESHOLD', '0.4')}",
        f"VAD_SILENCE_TIMEOUT={existing.get('VAD_SILENCE_TIMEOUT', '1.2')}",
        f"WORKSPACE_ROOT={existing.get('WORKSPACE_ROOT', '')}",
        f"WAKE_WORD={existing.get('WAKE_WORD', 'jarvis')}",
    ]

    with open(ENV_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")

    ok(f".env written to {ENV_FILE}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*54)
    print("  Welcome to Jarvis Setup")
    print("="*54)
    print("\n  This wizard will configure everything you need.")
    print("  It takes about 5-10 minutes on first run.")

    env = {}

    python = setup_venv()
    setup_ollama(env)
    setup_kokoro()
    setup_hardware(env)
    setup_microphone(env)
    setup_wake_word(env)
    setup_google()
    write_env(env)

    title("Setup complete!")
    print("""
  Everything is configured. To start Jarvis:

    Windows:
      .venv\\Scripts\\python.exe main.py

    Mac / Linux:
      .venv/bin/python main.py

  To re-run setup at any time:
      python setup.py
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Setup interrupted. Run python setup.py to continue.\n")