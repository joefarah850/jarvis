<div align="center">

```
                        ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
                        ░                                                     ░
                        ░       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗       ░
                        ░       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝       ░
                        ░       ██║███████║██████╔╝██║   ██║██║███████╗       ░
                        ░  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║       ░
                        ░  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║       ░
                        ░   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝       ░
                        ░                                                     ░
                        ░       J U S T - A - R A T H E R - V E R Y -         ░
                        ░       I N T E L L I G E N T - S Y S T E M           ░
                        ░                                                     ░
                        ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

**A fully local, voice-controlled AI assistant inspired by Iron Man's J.A.R.V.I.S.**  
No cloud. No subscriptions. No sending your data anywhere.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-black?style=flat-square)](https://ollama.com)
[![Electron](https://img.shields.io/badge/UI-Electron-47848F?style=flat-square&logo=electron)](https://electronjs.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Mac%20%7C%20Linux-lightgrey?style=flat-square)](.)

</div>

---

## What is this?

Jarvis is a **fully offline voice AI assistant** that runs entirely on your machine. You speak, it listens, thinks, and responds — all without a single API call leaving your computer.

It comes with an **Iron Man-style HUD** built in Electron, a wake word, voice-to-voice responses, and a growing set of tools that let it actually *do things* — not just talk.

---

## Features

### 🎙 Voice Pipeline
- **Wake word detection** — say "Jarvis" to activate (configurable)
- **Speech-to-text** — faster-whisper running locally on GPU or CPU
- **Voice activity detection** — Silero VAD, no wasted transcriptions
- **Text-to-speech** — Kokoro TTS with a deep, natural voice

### 🧠 Local LLM
- Runs on **Ollama** — works with Qwen3, Llama 3.1, Mistral, Phi-4 and more
- Full **tool-calling** — Jarvis picks the right tool automatically
- **Conversation memory** — remembers context within and across sessions
- **Long-term memory** — extracts facts from conversations, validated by you before saving

### 🛠 Built-in Tools

| Tool | What it does |
|------|-------------|
| 📧 **Email** | Read, summarize, and send emails via Gmail |
| 📅 **Calendar** | Check upcoming events from Google Calendar |
| ✅ **Todo list** | Add, list, complete, and clear tasks |
| ⏰ **Reminders** | One-time and recurring reminders with voice + WhatsApp/email alerts |
| 🔍 **Web search** | Real-time search via DuckDuckGo + full page fetch |
| 🕐 **Time zones** | Current time in any city, calculated from system clock |
| 💬 **Messaging** | Send WhatsApp messages and Gmail via voice approval flow |
| 🖥 **System** | Open apps and files (Chrome, Spotify, VS Code, etc.) |
| 📁 **File editing** | Read, edit, append, and hot-reload code files by voice |
| 🗓 **Google Chat** | Send messages to spaces via webhooks |

### 🖥 Iron Man HUD
- Fullscreen dark overlay with scanlines and corner brackets
- Animated arc reactor orb — reacts to listening / thinking / speaking states
- Rotating radar sweep with crosshairs
- Live conversation transcript
- Todos, reminders, and memory panels
- Real-time CPU, RAM, time, and date display
- Voice waveform that animates when Jarvis speaks

### 🔒 Fully Local
- LLM runs on your machine via Ollama
- STT runs locally via faster-whisper
- TTS runs locally via Kokoro ONNX
- Google APIs are optional (Gmail, Calendar, Contacts)
- WhatsApp via browser automation — no third-party service

---

## Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.10+ | 3.12 |
| RAM | 8 GB | 16 GB |
| GPU | Optional | NVIDIA 6 GB VRAM (RTX 3060+) |
| Storage | 5 GB | 10 GB |
| Node.js | 18+ | 20+ (for Electron UI) |
| npm | 9+ | comes with Node.js |
| Ollama | Latest | Latest |

> **Apple Silicon Macs** work great — unified memory handles the LLM efficiently without a GPU.

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/joefarah850/jarvis.git
cd jarvis
```

### 2. Install Ollama

Download from [ollama.com/download](https://ollama.com/download) and install it.

### 3. Run setup

```bash
python setup.py
```

The setup wizard will:
- Create a virtual environment and install all Python dependencies
- Install Node.js / Electron UI dependencies (`npm install`)
- Download the Ollama model of your choice
- Download the Kokoro TTS voice model
- Detect your GPU and configure Whisper
- Detect your microphone
- Set your wake word
- Authenticate with Google (Gmail, Calendar, Contacts)
- Create `whatsapp_contacts.json` and `gchat_webhooks.json`
- Write your `.env` configuration file

### 4. Run Jarvis

**Windows** — double-click `run_jarvis.vbs`

**Mac** — double-click `run_jarvis.command` (first time: right-click → Open)

**Linux** — `bash run_jarvis.sh`

**Manual** (any platform):
```bash
# Terminal 1
python main.py

# Terminal 2
cd ui && npm start
```

---

## Google API Setup (optional)

For Gmail, Calendar, and Contacts you need a Google OAuth credentials file.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project named **Jarvis**
3. Enable these APIs: Gmail API, Google Calendar API, People API, Google Chat API
4. OAuth consent screen → External → add your email as test user
5. Add scopes: `gmail.readonly`, `gmail.send`, `calendar.readonly`, `contacts.readonly`
6. Credentials → Create → OAuth 2.0 Client ID → Desktop app → Download JSON
7. Save it as `credentials.json` in the repo root
8. Re-run `python setup.py` — it will open the browser for auth

---

## Configuration

All settings live in `.env` (created by setup.py):

```env
# LLM
OLLAMA_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434

# Speech recognition
WHISPER_MODEL=large-v3-turbo
WHISPER_DEVICE=cuda          # cuda | cpu
WHISPER_COMPUTE_TYPE=float16 # float16 | int8

# Voice
KOKORO_VOICE=am_michael      # am_michael | am_adam | am_eric

# Microphone (partial name match, leave blank to auto-detect)
AUDIO_DEVICE_NAME=Microphone (Realtek

# Wake word (leave blank to always listen)
WAKE_WORD=jarvis

# File workspace (Jarvis can read/edit files here)
WORKSPACE_ROOT=C:/Users/YourName/projects
```

---

## WhatsApp Setup

Jarvis sends WhatsApp messages via browser automation (no paid API needed).

1. Add contacts to `whatsapp_contacts.json`:
```json
{
  "mom": "+1234567890",
  "john": "+9876543210"
}
```
2. Or say: *"Add WhatsApp contact John, plus 961 71 234 567"*
3. Contacts without a saved number are auto-looked up from Google Contacts
4. First send opens Chrome for WhatsApp Web login — stays logged in after that

---

## Google Chat Setup

For sending to **Spaces** (most reliable):
1. Open a Space → Apps & integrations → Webhooks → Add webhook
2. Copy the URL
3. Add to `gchat_webhooks.json`:
```json
{
  "dev team": "https://chat.googleapis.com/v1/spaces/..."
}
```
4. Say: *"Send a Google Chat message to the dev team saying..."*

---

## Project Structure

```
jarvis/
├── main.py                    # Entry point — main voice loop
├── config.py                  # Settings from .env
├── setup.py                   # First-run setup wizard
├── run_jarvis.vbs             # Windows launcher (no terminal)
├── run_jarvis.command         # Mac launcher
├── run_jarvis.sh              # Linux launcher
│
├── agent/
│   ├── brain.py              # LLM + tool-calling loop
│   └── tools/
│       ├── email_tool.py     # Gmail read
│       ├── compose_tool.py   # Gmail send, WhatsApp, Google Chat
│       ├── calendar_tool.py  # Google Calendar
│       ├── todo_tool.py      # Local todo list
│       ├── reminder_tool.py  # Reminders with notifications
│       ├── search_tool.py    # Web search + page fetch
│       ├── time_tool.py      # Timezone conversion
│       ├── system_tool.py    # Open apps (cross-platform)
│       └── code_tool.py      # File editing + hot reload
│
├── audio/
│   ├── listener.py           # Microphone + VAD (cross-platform)
│   ├── transcriber.py        # faster-whisper STT
│   └── speaker.py            # Kokoro TTS
│
├── memory/
│   └── context.py            # Long-term memory store
│
├── ui/
│   ├── bridge.py             # WebSocket server → Electron
│   ├── package.json
│   └── src/
│       ├── main.js           # Electron main process
│       ├── preload.js
│       └── index.html        # Iron Man HUD
│
├── credentials.json           # Google OAuth (you provide)
├── whatsapp_contacts.json     # WhatsApp contacts
├── gchat_webhooks.json        # Google Chat webhooks
├── memory.json                # Long-term memory (auto-created)
├── todos.json                 # Todo list (auto-created)
└── reminders.json             # Reminders (auto-created)
```

---

## Adding New Tools

Adding a tool to Jarvis takes 3 steps:

**1. Create `agent/tools/my_tool.py`:**
```python
def my_function(param: str) -> str:
    # do something
    return "result"
```

**2. Add to `TOOLS` in `agent/brain.py`:**
```python
{
    "type": "function",
    "function": {
        "name": "my_function",
        "description": "What it does — the LLM reads this to decide when to call it",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "What param is"}
            },
            "required": ["param"],
        },
    },
},
```

**3. Add dispatch in `_dispatch_tool`:**
```python
elif name == "my_function":
    from agent.tools.my_tool import my_function
    return my_function(**args)
```

That's it — Jarvis picks up the tool automatically on next run (or say *"reload brain.py"* for instant hot reload).

---

## Voice Commands — Examples

```
"Jarvis, check my emails"
"Jarvis, what's on my calendar this week?"
"Jarvis, add buy groceries to my todo list"
"Jarvis, remind me to call John in 30 minutes"
"Jarvis, remind me to take medication at 9am every day"
"Jarvis, send a WhatsApp to Mom saying I'll be late"
"Jarvis, send an email to john@example.com about tomorrow's meeting"
"Jarvis, what time is it in Tokyo?"
"Jarvis, who won the Champions League?"
"Jarvis, open Spotify"
"Jarvis, add a new function to agent/tools/system_tool.py"
"Jarvis, what do you remember about me?"
"Jarvis, remember that I drive a Tesla"
```

---

## Models Tested

| Model | Size | Quality | Speed | Recommended for |
|-------|------|---------|-------|----------------|
| qwen3:8b | 5 GB | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Best overall |
| llama3.1:8b | 5 GB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Alternative |
| mistral:7b | 4 GB | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Low RAM |
| phi4:latest | 9 GB | ⭐⭐⭐⭐ | ⭐⭐⭐ | Strong reasoning |

---

## Known Limitations

- **WhatsApp browser automation** is fragile — WhatsApp Web's UI can change and break selectors
- **Google Chat DMs** via API require Google Workspace admin approval — webhooks work fine for Spaces
- **Hot reload** works for tools and brain, but audio pipeline changes require a restart
- **Wake word** is basic substring matching — not as reliable as dedicated wake word engines like Porcupine

---

## Roadmap

- [ ] Porcupine wake word integration (better accuracy)
- [ ] Spotify / music control tool
- [ ] Smart home integration (Home Assistant, Philips Hue)
- [ ] Screen capture and vision ("Jarvis, what's on my screen?")
- [ ] Multi-language support
- [ ] Electron app packager (distributable .exe / .dmg)
- [ ] Plugin marketplace

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss.

When adding a tool, follow the pattern in `agent/tools/` and update this README.

---

## License

MIT — do whatever you want, just don't sell it as your own product.

---

<div align="center">

*"Sometimes you gotta run before you can walk."*  
— Tony Stark

**Built with:** Python · Ollama · faster-whisper · Kokoro TTS · Silero VAD · Electron · Google APIs · Selenium

</div>
