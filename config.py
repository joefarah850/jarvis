from dotenv import load_dotenv
import os

load_dotenv()

# ── LLM ──────────────────────────────────────────────────────────────────────
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ── Whisper ───────────────────────────────────────────────────────────────────
WHISPER_MODEL        = os.getenv("WHISPER_MODEL", "large-v3-turbo")
WHISPER_LANGUAGE     = os.getenv("WHISPER_LANGUAGE", "en")
WHISPER_DEVICE       = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

# ── TTS ───────────────────────────────────────────────────────────────────────
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "am_michael")

# ── Audio input ───────────────────────────────────────────────────────────────
AUDIO_DEVICE_NAME = os.getenv("AUDIO_DEVICE_NAME", "")

# ── VAD ───────────────────────────────────────────────────────────────────────
VAD_THRESHOLD       = float(os.getenv("VAD_THRESHOLD", "0.4"))
VAD_SILENCE_TIMEOUT = float(os.getenv("VAD_SILENCE_TIMEOUT", "1.2"))

# ── File workspace ────────────────────────────────────────────────────────────
# Root directory Jarvis can read/edit files in.
# Defaults to repo root. Set to a broader path to allow editing other projects.
# Example in .env: WORKSPACE_ROOT=C:/Users/<user>/Desktop
WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", "")

# ── Assistant identity ───────────────────────────────────────────────────────
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Jarvis")

# ── Wake word ────────────────────────────────────────────────────────────────
# Set to a word Jarvis must hear before listening. Leave empty to always listen.
WAKE_WORD = os.getenv("WAKE_WORD", "")
