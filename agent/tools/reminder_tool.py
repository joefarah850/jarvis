"""
Reminder tool — set one-time and recurring reminders.
Fires via voice (Jarvis speaks) + optional WhatsApp/email notification.
Persists to reminders.json so they survive restarts.

Runs a background thread that checks every 30 seconds.
"""
import json
import threading
import time
import re
from datetime import datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

_REPO_ROOT     = Path(__file__).resolve().parent.parent.parent
REMINDERS_FILE = _REPO_ROOT / "reminders.json"

# Injected from main.py
_speaker       = None
_listen_fn     = None
_transcribe_fn = None
_brain         = None   # for sending WhatsApp/email on fire

_checker_thread = None
_lock           = threading.Lock()


def set_reminder_io(speaker, listen_fn, transcribe_fn, brain=None):
    global _speaker, _listen_fn, _transcribe_fn, _brain
    _speaker       = speaker
    _listen_fn     = listen_fn
    _transcribe_fn = transcribe_fn
    _brain         = brain


# ── Storage ───────────────────────────────────────────────────────────────────

def _load() -> list[dict]:
    if not REMINDERS_FILE.exists():
        return []
    with open(REMINDERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(reminders: list[dict]):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=2)


def _next_id() -> int:
    reminders = _load()
    return max((r["id"] for r in reminders), default=0) + 1


# ── Time parsing ──────────────────────────────────────────────────────────────

def _parse_time(time_str: str) -> datetime | None:
    """
    Parse natural language time expressions into a datetime.
    Examples:
      "in 10 minutes", "in 2 hours", "at 3pm", "at 14:30",
      "tomorrow at 9am", "in 30 seconds"
    """
    now = datetime.now()
    s   = time_str.lower().strip()

    # "in X seconds/minutes/hours/days"
    m = re.search(r'in\s+(\d+)\s*(second|minute|hour|day)s?', s)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {
            "second": timedelta(seconds=n),
            "minute": timedelta(minutes=n),
            "hour":   timedelta(hours=n),
            "day":    timedelta(days=n),
        }[unit]
        return now + delta

    # "at HH:MM" or "at H:MMam/pm" or "at Xpm/am"
    m = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', s)
    if m:
        hour   = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm   = m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if "tomorrow" in s:
            target += timedelta(days=1)
        elif target <= now:
            target += timedelta(days=1)   # assume next occurrence
        return target

    # "tomorrow at ..." already handled above, but "tomorrow" alone
    if "tomorrow" in s:
        return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)

    return None


def _parse_recurrence(recurrence_str: str) -> str | None:
    """
    Parse recurrence into a canonical string.
    Returns: "daily", "weekly", "hourly", "weekdays", None
    """
    s = recurrence_str.lower()
    if any(w in s for w in ["every day", "daily", "every morning", "every night"]):
        return "daily"
    if any(w in s for w in ["every week", "weekly", "every monday", "every tuesday",
                              "every wednesday", "every thursday", "every friday"]):
        return "weekly"
    if any(w in s for w in ["every hour", "hourly"]):
        return "hourly"
    if any(w in s for w in ["weekday", "every weekday", "monday to friday"]):
        return "weekdays"
    return None


def _next_fire(fire_time: str, recurrence: str | None) -> str:
    """Calculate next fire time for recurring reminders."""
    now  = datetime.now()
    base = datetime.fromisoformat(fire_time)

    if not recurrence:
        return fire_time

    if recurrence == "hourly":
        while base <= now:
            base += timedelta(hours=1)
    elif recurrence == "daily":
        while base <= now:
            base += timedelta(days=1)
    elif recurrence == "weekly":
        while base <= now:
            base += timedelta(weeks=1)
    elif recurrence == "weekdays":
        while base <= now or base.weekday() >= 5:
            base += timedelta(days=1)

    return base.isoformat()

def _get_name() -> str:
    """Get the assistant name from config."""
    try:
        from config import ASSISTANT_NAME
        return ASSISTANT_NAME
    except Exception:
        return "Jarvis"

# ── CRUD ──────────────────────────────────────────────────────────────────────

def set_reminder(
    message: str,
    when: str,
    recurrence: str = "",
    notify_whatsapp: str = "",
    notify_email: str = "",
) -> str:
    """
    Set a reminder.
    - message: what Jarvis should say when it fires
    - when: natural language time ("in 10 minutes", "at 3pm", "tomorrow at 9am")
    - recurrence: optional ("daily", "weekly", "hourly", "weekdays")
    - notify_whatsapp: phone number or contact name to also send a WhatsApp message
    - notify_email: email address to also send an email
    """
    fire_dt = _parse_time(when)
    if not fire_dt:
        return (
            f'Could not parse time: "{when}". '
            'Try: "in 10 minutes", "at 3pm", "tomorrow at 9am".'
        )

    recur = _parse_recurrence(recurrence) if recurrence else None

    reminder = {
        "id":              _next_id(),
        "message":         message,
        "fire_time":       fire_dt.isoformat(),
        "recurrence":      recur,
        "notify_whatsapp": notify_whatsapp,
        "notify_email":    notify_email,
        "active":          True,
        "created":         datetime.now().isoformat(),
    }

    with _lock:
        reminders = _load()
        reminders.append(reminder)
        _save(reminders)

    fire_str = fire_dt.strftime("%I:%M %p on %A %B %d")
    recur_str = f", repeating {recur}" if recur else ""
    return f"Reminder #{reminder['id']} set for {fire_str}{recur_str}: \"{message}\""


def list_reminders() -> str:
    reminders = [r for r in _load() if r.get("active")]
    if not reminders:
        return "No active reminders."
    lines = []
    for r in reminders:
        dt      = datetime.fromisoformat(r["fire_time"])
        time_str = dt.strftime("%I:%M %p, %b %d")
        recur   = f" [{r['recurrence']}]" if r.get("recurrence") else ""
        lines.append(f"#{r['id']}{recur} at {time_str}: {r['message']}")
    return "Active reminders:\n" + "\n".join(lines)


def cancel_reminder(reminder_id: int) -> str:
    with _lock:
        reminders = _load()
        for r in reminders:
            if r["id"] == reminder_id:
                r["active"] = False
                _save(reminders)
                return f"Reminder #{reminder_id} cancelled."
    return f"Reminder #{reminder_id} not found."


# ── Firing ────────────────────────────────────────────────────────────────────

def _fire_reminder(reminder: dict):
    """Called when a reminder's time has come."""
    msg = reminder["message"]

    # Voice alert
    if _speaker:
        _speaker.speak(f"Reminder: {msg}")
    else:
        print(f"\n[REMINDER] {msg}\n")

    # WhatsApp notification
    if reminder.get("notify_whatsapp") and _brain:
        try:
            from agent.tools.compose_tool import send_whatsapp
            send_whatsapp(reminder["notify_whatsapp"], f"Reminder: {msg}")
        except Exception as e:
            print(f"[Reminder] WhatsApp notify failed: {e}")

    # Email notification
    if reminder.get("notify_email") and _brain:
        try:
            from agent.tools.compose_tool import send_gmail
            send_gmail(
                reminder["notify_email"],
                f"Subject: Reminder\n{msg}"
            )
        except Exception as e:
            print(f"[Reminder] Email notify failed: {e}")

    # Handle recurrence or deactivate
    with _lock:
        reminders = _load()
        for r in reminders:
            if r["id"] == reminder["id"]:
                if r.get("recurrence"):
                    r["fire_time"] = _next_fire(r["fire_time"], r["recurrence"])
                    print(f"[Reminder] #{r['id']} rescheduled to {r['fire_time']}")
                else:
                    r["active"] = False
        _save(reminders)


# ── Background checker ────────────────────────────────────────────────────────

def _checker_loop():
    """Runs in background, checks every 30 seconds for due reminders."""
    while True:
        try:
            now = datetime.now()
            with _lock:
                reminders = _load()

            for r in reminders:
                if not r.get("active"):
                    continue
                fire_time = datetime.fromisoformat(r["fire_time"])
                if fire_time <= now:
                    threading.Thread(
                        target=_fire_reminder,
                        args=(r,),
                        daemon=True,
                    ).start()

        except Exception as e:
            print(f"[Reminder] Checker error: {e}")

        time.sleep(30)


def start_reminder_checker():
    """Start the background reminder checker thread. Call once from main.py."""
    global _checker_thread
    if _checker_thread and _checker_thread.is_alive():
        return
    _checker_thread = threading.Thread(target=_checker_loop, daemon=True)
    _checker_thread.start()
    print(f"[{_get_name()}] Background checker started")