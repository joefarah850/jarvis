"""
Jarvis Setup Wizard
-------------------
Run this once after cloning the repo. It will:
  1. Create a virtual environment and install Python dependencies
  1b. Install Node.js / Electron UI dependencies
  2. Check / download Ollama and the LLM model
  3. Download the Kokoro TTS model files
  4. Detect your hardware and set Whisper settings
  5. Detect your microphone
  6. Set wake word and voice
  7. Configure workspace root for file editing
  8. Authenticate all Google services (Gmail, Calendar, Contacts, Gmail Send)
  9. Set up WhatsApp contacts file
 10. Set up Google Chat webhooks file
 11. Write your .env file

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

REPO_ROOT  = Path(__file__).parent.resolve()
ENV_FILE   = REPO_ROOT / ".env"
IS_WINDOWS = platform.system() == "Windows"
IS_MAC     = platform.system() == "Darwin"

# ── Helpers ───────────────────────────────────────────────────────────────────

def title(text: str):
    print(f"\n{'='*54}")
    print(f"  {text}")
    print(f"{'='*54}")

def step(text: str):   print(f"\n▶  {text}")
def ok(text: str):     print(f"   ✓  {text}")
def warn(text: str):   print(f"   ⚠  {text}")
def info(text: str):   print(f"      {text}")

def ask(prompt: str, default: str = "") -> str:
    if default:
        val = input(f"   {prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"   {prompt}: ").strip()

def confirm(prompt: str, default: bool = True) -> bool:
    suffix = "(Y/n)" if default else "(y/N)"
    val = input(f"   {prompt} {suffix}: ").strip().lower()
    if not val:
        return default
    return val.startswith("y")

def run(cmd, check=True, capture=False, **kwargs):
    return subprocess.run(
        cmd, check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        **kwargs
    )

def _download(url: str, dest: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        total      = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r   {pct:.1f}% ({downloaded//1_000_000}MB / {total//1_000_000}MB)",
                          end="", flush=True)
    print()


# ── Step 1: Virtual environment ───────────────────────────────────────────────

def setup_venv() -> Path:
    title("Step 1 — Virtual environment & dependencies")

    venv_path = REPO_ROOT / ".venv"
    if venv_path.exists():
        ok(f"Virtual environment already exists")
    else:
        step("Creating virtual environment...")
        run([sys.executable, "-m", "venv", str(venv_path)])
        ok("Virtual environment created")

    if IS_WINDOWS:
        pip    = venv_path / "Scripts" / "pip.exe"
        python = venv_path / "Scripts" / "python.exe"
    else:
        pip    = venv_path / "bin" / "pip"
        python = venv_path / "bin" / "python"

    step("Installing dependencies (this may take a few minutes)...")
    run([str(pip), "install", "--upgrade", "pip", "-q"])
    run([str(pip), "install", "-r", str(REPO_ROOT / "requirements.txt"), "-q"])
    ok("All dependencies installed")
    return python


# ── Step 1b: Node.js / npm ───────────────────────────────────────────────────

def setup_node():
    title("Step 1b — Node.js & Electron UI")

    # Check Node.js
    if shutil.which("node") is None:
        warn("Node.js not found.")
        info("Please install Node.js from https://nodejs.org (LTS version)")
        if confirm("Open Node.js download page now?"):
            import webbrowser
            webbrowser.open("https://nodejs.org")
        info("After installing Node.js, re-run this setup script.")
        sys.exit(0)
    else:
        try:
            result = run(["node", "--version"], capture=True, check=False)
            version = result.stdout.decode().strip() if result.stdout else "unknown"
            ok(f"Node.js installed: {version}")
        except Exception:
            ok("Node.js installed")

    # Check npm
    if shutil.which("npm") is None:
        warn("npm not found — it should come with Node.js. Please reinstall Node.js.")
        sys.exit(0)

    # Install Electron dependencies
    ui_dir = REPO_ROOT / "ui"
    node_modules = ui_dir / "node_modules"

    if node_modules.exists() and (node_modules / "electron").exists():
        ok("Electron dependencies already installed")
    else:
        step("Installing Electron dependencies (this may take a minute)...")
        run(["npm", "install"], cwd=str(ui_dir))
        ok("Electron dependencies installed")


# ── Step 2: Ollama ────────────────────────────────────────────────────────────

def setup_ollama(env: dict):
    title("Step 2 — Ollama & LLM model")

    if shutil.which("ollama") is None:
        warn("Ollama not found.")
        info("Please install Ollama from https://ollama.com/download")
        info("After installing, re-run this setup script.")
        if confirm("Open the Ollama download page now?"):
            import webbrowser
            webbrowser.open("https://ollama.com/download")
        sys.exit(0)
    else:
        ok("Ollama is installed")

    try:
        result = run(["ollama", "list"], capture=True, check=False)
        output = result.stdout.decode() if result.stdout else ""
    except Exception:
        output = ""

    default_model = "qwen3:8b"
    info(f"Recommended model: {default_model} (fast, strong tool-calling)")
    info("Alternatives: llama3.1:8b, mistral:7b, phi4:latest")
    model = ask("Which Ollama model do you want to use?", default_model)

    if model.lower() in output.lower():
        ok(f"{model} is already downloaded")
    else:
        step(f"Pulling {model} (this may take several minutes)...")
        run(["ollama", "pull", model])
        ok(f"{model} downloaded")

    env["OLLAMA_MODEL"]    = model
    env["OLLAMA_BASE_URL"] = "http://localhost:11434"


# ── Step 3: Kokoro TTS ────────────────────────────────────────────────────────

def setup_kokoro():
    title("Step 3 — Kokoro TTS model files")

    base_url   = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
    model_file = "kokoro-v1.0.fp16-gpu.onnx" if IS_WINDOWS else "kokoro-v1.0.fp16.onnx"
    model_desc = "Windows GPU (fp16)" if IS_WINDOWS else "Mac/Linux CPU (fp16)"
    model_path = REPO_ROOT / model_file
    voices     = REPO_ROOT / "voices-v1.0.bin"

    if model_path.exists():
        ok(f"Model file already exists: {model_file}")
    else:
        step(f"Downloading Kokoro model ({model_desc})...")
        _download(f"{base_url}/{model_file}", model_path)
        ok(f"Downloaded {model_file}")

    if voices.exists():
        ok("Voices file already exists")
    else:
        step("Downloading voices file...")
        _download(f"{base_url}/voices-v1.0.bin", voices)
        ok("Downloaded voices-v1.0.bin")


# ── Step 4: Hardware ──────────────────────────────────────────────────────────

def setup_hardware(env: dict):
    title("Step 4 — Hardware detection")

    system          = platform.system()
    whisper_device  = "cpu"
    whisper_compute = "int8"

    if system == "Windows":
        try:
            import torch
            if torch.cuda.is_available():
                ok(f"NVIDIA GPU: {torch.cuda.get_device_name(0)}")
                whisper_device  = "cuda"
                whisper_compute = "float16"
            else:
                warn("No CUDA GPU — using CPU")
        except ImportError:
            warn("PyTorch not available yet — defaulting to CPU")
    elif system == "Darwin":
        ok("Mac detected — using optimised CPU int8")
    else:
        try:
            import torch
            if torch.cuda.is_available():
                ok("NVIDIA GPU detected")
                whisper_device  = "cuda"
                whisper_compute = "float16"
            else:
                warn("No CUDA GPU — using CPU")
        except ImportError:
            warn("PyTorch not available yet — defaulting to CPU")

    ok(f"Whisper: {whisper_device} / {whisper_compute}")
    env["WHISPER_DEVICE"]       = whisper_device
    env["WHISPER_COMPUTE_TYPE"] = whisper_compute
    env["WHISPER_MODEL"]        = "large-v3-turbo"
    env["WHISPER_LANGUAGE"]     = ask("What language will you mostly speak?", "en")


# ── Step 5: Microphone ────────────────────────────────────────────────────────

def setup_microphone(env: dict):
    title("Step 5 — Microphone")

    try:
        import sounddevice as sd
        devices    = sd.query_devices()
        input_devs = [
            (i, d) for i, d in enumerate(devices)
            if d['max_input_channels'] > 0
            and 'stereo mix' not in d['name'].lower()
            and 'loopback'   not in d['name'].lower()
            and 'output'     not in d['name'].lower()
        ]

        if not input_devs:
            warn("No input devices found.")
            env["AUDIO_DEVICE_NAME"] = ""
            return

        info("Available microphones:")
        for i, (_, d) in enumerate(input_devs):
            info(f"  {i+1}. {d['name']}")

        if len(input_devs) == 1:
            ok(f"Only one mic found: {input_devs[0][1]['name']}")
            env["AUDIO_DEVICE_NAME"] = input_devs[0][1]['name'][:40]
        else:
            choice = ask("Which mic? (number, or Enter to auto-detect)", "")
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(input_devs):
                    env["AUDIO_DEVICE_NAME"] = input_devs[idx][1]['name'][:40]
                    ok(f"Selected: {env['AUDIO_DEVICE_NAME']}")
                    return
            env["AUDIO_DEVICE_NAME"] = ""
            ok("Will auto-detect on startup")

    except Exception as e:
        warn(f"Could not list audio devices: {e}")
        env["AUDIO_DEVICE_NAME"] = ""


# ── Step 6: Wake word & voice ─────────────────────────────────────────────────

def setup_wake_word(env: dict):
    title("Step 6 — Wake word & voice")

    name = ask("What should your assistant be called?", "Jarvis")
    env["ASSISTANT_NAME"] = name
    ok(f"Assistant name: {name}")

    info(f"\nA wake word means {name} only listens after you say it.")
    info("Leave blank to always listen.")
    wake_word = ask(f"Wake word (e.g. '{name.lower()}', or Enter to skip)", name.lower())
    env["WAKE_WORD"] = wake_word
    ok(f"Wake word: '{wake_word}'" if wake_word else "Always-listening mode")

    info("\nAvailable voices: am_michael (deep), am_adam (deeper), am_eric (warm)")
    env["KOKORO_VOICE"] = ask("TTS voice", "am_michael")


# ── Step 7: Workspace root ────────────────────────────────────────────────────

def setup_workspace(env: dict):
    title("Step 7 — File workspace")

    info("Jarvis can read and edit files on your computer.")
    info("Set the root directory it can access.")
    info("Example: C:/Users/Joe/Desktop/Projects  or  /Users/joe/projects")
    info("Leave blank to restrict to the Jarvis repo folder only.")

    workspace = ask("Workspace root directory (or Enter to skip)", "")
    if workspace and not Path(workspace).exists():
        warn(f"Directory not found: {workspace} — leaving blank")
        workspace = ""
    env["WORKSPACE_ROOT"] = workspace
    ok(f"Workspace: {workspace}" if workspace else "Workspace: repo root only")


# ── Step 8: Google OAuth ──────────────────────────────────────────────────────

# All scopes in one token — simpler than multiple tokens
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]

def _google_auth(creds_path: Path, token_path: Path, scopes: list, label: str) -> bool:
    """Authenticate with Google and save token. Returns True on success."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)

        if creds and creds.valid:
            ok(f"{label} already authenticated")
            return True

        if creds and creds.expired and creds.refresh_token:
            step(f"Refreshing {label} token...")
            creds.refresh(Request())
        else:
            step(f"Authenticating {label} (browser will open)...")
            flow  = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        ok(f"{label} authenticated")
        return True

    except Exception as e:
        warn(f"{label} auth failed: {e}")
        return False


def setup_google():
    title("Step 8 — Google Authentication")

    creds_path = REPO_ROOT / "credentials.json"

    if not creds_path.exists():
        print("""
   To use Gmail, Calendar, and Contacts you need Google OAuth credentials.

   Steps:
   1. Go to https://console.cloud.google.com and create a project named 'Jarvis'
   2. APIs & Services → Enable APIs → enable ALL of:
      - Gmail API
      - Google Calendar API
      - People API
      - Google Chat API
   3. APIs & Services → OAuth consent screen
      - User type: External
      - App name: Jarvis
      - Add your email as a test user
      - Scopes: gmail.readonly, gmail.send, calendar.readonly,
                contacts.readonly, chat.messages.create, chat.spaces.create
   4. APIs & Services → Credentials
      - Create credentials → OAuth 2.0 Client ID → Desktop app
      - Download JSON → save as 'credentials.json' in this folder
""")
        if confirm("Open Google Cloud Console now?"):
            import webbrowser
            webbrowser.open("https://console.cloud.google.com")
        input("\n   Press Enter once credentials.json is saved here...")

        if not creds_path.exists():
            warn("credentials.json not found — skipping Google auth.")
            warn("Re-run setup.py when ready.")
            return

    ok("credentials.json found")

    # Single token for Gmail read + send + Calendar + Contacts
    _google_auth(
        creds_path,
        REPO_ROOT / "token_gmail.json",
        GOOGLE_SCOPES,
        "Gmail + Calendar + Contacts"
    )

    # Separate token for Gmail send (compose_tool uses its own token)
    _google_auth(
        creds_path,
        REPO_ROOT / "token_gmail_send.json",
        ["https://www.googleapis.com/auth/gmail.send"],
        "Gmail Send"
    )

    # Separate token for Contacts lookup
    _google_auth(
        creds_path,
        REPO_ROOT / "token_contacts.json",
        ["https://www.googleapis.com/auth/contacts.readonly"],
        "Google Contacts"
    )

    # Calendar token
    _google_auth(
        creds_path,
        REPO_ROOT / "token_calendar.json",
        ["https://www.googleapis.com/auth/calendar.readonly"],
        "Google Calendar"
    )

    # Google Chat API (optional — only works with Workspace accounts)
    if confirm("Do you have a Google Workspace account (company email)?", False):
        _google_auth(
            creds_path,
            REPO_ROOT / "token_gchat_dm.json",
            [
                "https://www.googleapis.com/auth/chat.messages.create",
                "https://www.googleapis.com/auth/chat.spaces.create",
            ],
            "Google Chat"
        )
    else:
        ok("Skipping Google Chat API (use webhooks for spaces, WhatsApp for DMs)")


# ── Step 9: WhatsApp contacts ─────────────────────────────────────────────────

def setup_whatsapp():
    title("Step 9 — WhatsApp contacts")

    contacts_file = REPO_ROOT / "whatsapp_contacts.json"

    if contacts_file.exists():
        with open(contacts_file, encoding="utf-8") as f:
            existing = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        ok(f"whatsapp_contacts.json exists ({len(existing)} contacts)")
        return

    info("WhatsApp contacts map spoken names to phone numbers.")
    info("Jarvis will also auto-lookup from Google Contacts.")
    info("You can add contacts later by saying: 'add WhatsApp contact [name] [number]'")

    contacts = {}
    if confirm("Add a WhatsApp contact now?", False):
        while True:
            name  = ask("Contact name (or Enter to finish)", "")
            if not name:
                break
            phone = ask(f"Phone number for {name} (with country code, e.g. +96171234567)")
            if phone:
                contacts[name.lower()] = phone
                ok(f"Added: {name}")
            if not confirm("Add another?", False):
                break

    with open(contacts_file, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2)
    ok(f"whatsapp_contacts.json created ({len(contacts)} contacts)")


# ── Step 10: Google Chat webhooks ─────────────────────────────────────────────

def setup_gchat_webhooks():
    title("Step 10 — Google Chat webhooks (for Spaces)")

    webhooks_file = REPO_ROOT / "gchat_webhooks.json"

    if webhooks_file.exists():
        with open(webhooks_file, encoding="utf-8") as f:
            existing = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        ok(f"gchat_webhooks.json exists ({len(existing)} webhooks)")
        return

    info("Webhooks let Jarvis send messages to Google Chat Spaces.")
    info("To get a webhook: open a Space → Apps & integrations → Webhooks → Add")
    info("You can add webhooks later by saying: 'add Google Chat webhook for [name]'")

    webhooks = {}
    if confirm("Add a Google Chat webhook now?", False):
        while True:
            name = ask("Space name (e.g. 'dev team', or Enter to finish)", "")
            if not name:
                break
            url = ask(f"Webhook URL for '{name}'")
            if url.startswith("https://"):
                webhooks[name.lower()] = url
                ok(f"Added: {name}")
            else:
                warn("Invalid URL — skipping")
            if not confirm("Add another?", False):
                break

    with open(webhooks_file, "w", encoding="utf-8") as f:
        json.dump(webhooks, f, indent=2)
    ok(f"gchat_webhooks.json created ({len(webhooks)} webhooks)")


# ── Step 11: Write .env ───────────────────────────────────────────────────────

def write_env(env: dict):
    title("Step 11 — Writing .env")

    existing = {}
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        existing[k.strip()] = v.strip()
        except Exception:
            pass

    existing.update(env)

    lines = [
        "# Jarvis configuration — generated by setup.py",
        "",
        "# ── LLM ──────────────────────────────────────────────────",
        f"OLLAMA_MODEL={existing.get('OLLAMA_MODEL', 'qwen3:8b')}",
        f"OLLAMA_BASE_URL={existing.get('OLLAMA_BASE_URL', 'http://localhost:11434')}",
        "",
        "# ── Whisper STT ───────────────────────────────────────────",
        f"WHISPER_MODEL={existing.get('WHISPER_MODEL', 'large-v3-turbo')}",
        f"WHISPER_LANGUAGE={existing.get('WHISPER_LANGUAGE', 'en')}",
        f"WHISPER_DEVICE={existing.get('WHISPER_DEVICE', 'cpu')}",
        f"WHISPER_COMPUTE_TYPE={existing.get('WHISPER_COMPUTE_TYPE', 'int8')}",
        "",
        "# ── TTS ───────────────────────────────────────────────────",
        f"KOKORO_VOICE={existing.get('KOKORO_VOICE', 'am_michael')}",
        "",
        "# ── Audio input ───────────────────────────────────────────",
        f"AUDIO_DEVICE_NAME={existing.get('AUDIO_DEVICE_NAME', '')}",
        f"VAD_THRESHOLD={existing.get('VAD_THRESHOLD', '0.4')}",
        f"VAD_SILENCE_TIMEOUT={existing.get('VAD_SILENCE_TIMEOUT', '1.2')}",
        "",
        "# ── Wake word ─────────────────────────────────────────────",
        f"WAKE_WORD={existing.get('WAKE_WORD', 'jarvis')}",
        "",
        "# ── File workspace ───────────────────────────────────────",
        f"WORKSPACE_ROOT={existing.get('WORKSPACE_ROOT', '')}",
    ]

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    ok(f".env written to {ENV_FILE}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*54)
    print("  Welcome to Jarvis Setup")
    print("="*54)
    print("\n  This wizard configures everything you need.")
    print("  It takes about 5-10 minutes on first run.\n")

    env = {}

    setup_venv()
    setup_node()
    setup_ollama(env)
    setup_kokoro()
    setup_hardware(env)
    setup_microphone(env)
    setup_wake_word(env)
    setup_workspace(env)
    setup_google()
    setup_whatsapp()
    setup_gchat_webhooks()
    write_env(env)

    title("Setup complete!")
    print(f"""
  Everything is configured. To start Jarvis:

    Windows:   .venv\\Scripts\\python.exe main.py
    Mac/Linux: .venv/bin/python main.py

  To re-run setup:  python setup.py

  Files created:
    .env                    — configuration
    token_gmail.json        — Gmail auth
    token_gmail_send.json   — Gmail send auth
    token_calendar.json     — Calendar auth
    token_contacts.json     — Contacts auth
    whatsapp_contacts.json  — WhatsApp contacts
    gchat_webhooks.json     — Google Chat webhooks
    reminders.json          — Reminders (created on first use)
    memory.json             — Long-term memory (created on first use)
    todos.json              — Todo list (created on first use)
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Setup interrupted. Run python setup.py to continue.\n")