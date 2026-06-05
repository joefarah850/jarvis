"""
WebSocket bridge — broadcasts Jarvis state to the Electron HUD.
Runs as a background thread inside main.py.

Events sent to UI:
  {"type": "status",      "value": "listening"|"thinking"|"speaking"|"idle"}
  {"type": "transcript",  "role": "user"|"jarvis", "text": "..."}
  {"type": "todos",       "items": [...]}
  {"type": "reminders",   "items": [...]}
  {"type": "memory",      "facts": [...]}
  {"type": "stats",       "cpu": 42, "ram": 68, "time": "09:41", "date": "..."}

Commands received from UI:
  {"type": "mute"}
  {"type": "unmute"}
  {"type": "clear_transcript"}
"""

import json
import threading
import asyncio
import time
import platform
from datetime import datetime
from pathlib import Path

_clients     = set()
_loop        = None
_status      = "idle"
_transcript  = []   # list of {"role": ..., "text": ...}
_lock        = threading.Lock()

# Callbacks registered by main.py
_on_mute     = None
_on_unmute   = None


def set_callbacks(on_mute=None, on_unmute=None):
    global _on_mute, _on_unmute
    _on_mute   = on_mute
    _on_unmute = on_unmute


# ── Public API (called from main.py / brain.py) ───────────────────────────────

def set_status(status: str):
    """Call with: 'idle', 'listening', 'thinking', 'speaking'"""
    global _status
    _status = status
    _broadcast({"type": "status", "value": status})


def add_transcript(role: str, text: str):
    """Add a line to the conversation transcript."""
    entry = {"role": role, "text": text, "time": datetime.now().strftime("%H:%M:%S")}
    with _lock:
        _transcript.append(entry)
        if len(_transcript) > 50:   # keep last 50 lines
            _transcript.pop(0)
    _broadcast({"type": "transcript", **entry})


def push_todos():
    """Push current todo list to UI."""
    try:
        from agent.tools.todo_tool import _load
        todos = [t for t in _load() if not t.get("done")]
        _broadcast({"type": "todos", "items": todos})
    except Exception:
        pass


def push_reminders():
    """Push active reminders to UI."""
    try:
        from agent.tools.reminder_tool import _load
        from datetime import datetime
        reminders = []
        for r in _load():
            if r.get("active"):
                dt = datetime.fromisoformat(r["fire_time"])
                reminders.append({
                    "id":        r["id"],
                    "message":   r["message"],
                    "fire_time": dt.strftime("%I:%M %p, %b %d"),
                    "recurrence": r.get("recurrence", ""),
                })
        _broadcast({"type": "reminders", "items": reminders})
    except Exception:
        pass


def push_memory():
    """Push memory facts to UI."""
    try:
        from memory.context import load_memory
        facts = load_memory().get("facts", [])
        _broadcast({"type": "memory", "facts": [f["fact"] for f in facts]})
    except Exception:
        pass


# ── WebSocket server ──────────────────────────────────────────────────────────

async def _handler(websocket):
    global _clients
    _clients.add(websocket)
    try:
        # Send current state immediately on connect
        await websocket.send(json.dumps({"type": "status", "value": _status}))
        for entry in _transcript[-20:]:
            await websocket.send(json.dumps({"type": "transcript", **entry}))

        # Send stats immediately so UI doesn't wait for the loop
        try:
            import psutil
            from datetime import datetime as _dt
            now = _dt.now()
            await websocket.send(json.dumps({
                "type": "stats",
                "cpu":  round(psutil.cpu_percent(interval=None)),
                "ram":  round(psutil.virtual_memory().percent),
                "time": now.strftime("%I:%M %p"),
                "date": now.strftime("%a %b %d"),
            }))
        except Exception:
            pass

        push_todos()
        push_reminders()
        push_memory()

        async for message in websocket:
            try:
                cmd = json.loads(message)
                if cmd.get("type") == "mute" and _on_mute:
                    _on_mute()
                elif cmd.get("type") == "unmute" and _on_unmute:
                    _on_unmute()
                elif cmd.get("type") == "clear_transcript":
                    with _lock:
                        _transcript.clear()
                    _broadcast({"type": "clear_transcript"})
            except Exception:
                pass
    except Exception:
        pass
    finally:
        _clients.discard(websocket)


def _broadcast(data: dict):
    """Send a message to all connected UI clients."""
    if not _clients or not _loop:
        return
    msg = json.dumps(data)
    asyncio.run_coroutine_threadsafe(_broadcast_async(msg), _loop)


async def _broadcast_async(msg: str):
    if not _clients:
        return
    dead = set()
    for ws in list(_clients):
        try:
            await ws.send(msg)
        except Exception:
            dead.add(ws)
    _clients -= dead


async def _stats_loop():
    """Send system stats every 2 seconds."""
    # Prime psutil CPU measurement
    try:
        import psutil
        psutil.cpu_percent(interval=None)
    except ImportError:
        pass

    while True:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
        except ImportError:
            cpu, ram = 0, 0

        now = datetime.now()
        _broadcast({
            "type": "stats",
            "cpu":  round(cpu),
            "ram":  round(ram),
            "time": now.strftime("%I:%M %p"),
            "date": now.strftime("%a %b %d"),
        })
        await asyncio.sleep(2)


async def _main(host: str, port: int):
    global _loop
    _loop = asyncio.get_event_loop()

    try:
        import websockets
        async with websockets.serve(_handler, host, port):
            print(f"[UI Bridge] WebSocket server running on ws://{host}:{port}")
            await _stats_loop()
    except ImportError:
        print("[UI Bridge] websockets not installed — run: pip install websockets psutil")


def start_bridge(host: str = "localhost", port: int = 6789):
    """Start the WebSocket bridge in a background thread."""
    def _run():
        asyncio.run(_main(host, port))
    t = threading.Thread(target=_run, daemon=True, name="ui-bridge")
    t.start()
    # Give the server a moment to bind the port
    time.sleep(0.5)
    print("[UI Bridge] Started — connect Electron UI to ws://localhost:6789")