"""
Message composer — drafts messages via LLM, reads them aloud,
waits for voice approval before sending.

Supports: Gmail, Google Chat, WhatsApp (browser automation)
"""
import re
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OLLAMA_MODEL, OLLAMA_BASE_URL

# Repo root — resolved once at import time so it works regardless of cwd
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
from ollama import Client

client = Client(host=OLLAMA_BASE_URL)

# Injected at runtime by brain.py
_speaker      = None
_listen_fn    = None
_transcribe_fn = None


def set_io(speaker, listen_fn, transcribe_fn):
    """Called from main.py to wire up audio I/O for the approval loop."""
    global _speaker, _listen_fn, _transcribe_fn
    _speaker       = speaker
    _listen_fn     = listen_fn
    _transcribe_fn = transcribe_fn


# ── Message drafting ──────────────────────────────────────────────────────────

def _draft(platform: str, recipient: str, intent: str, context: str = "") -> str:
    """Ask the LLM to write the message."""
    platform_hints = {
        "gmail":       "Write a professional email. Include a subject line prefixed with 'Subject:' on the first line, then the body.",
        "google chat": "Write a short, friendly Google Chat message. No subject line needed. Conversational tone.",
        "whatsapp":    "Write a short, natural WhatsApp message. Casual and concise.",
    }
    hint = platform_hints.get(platform.lower(), "Write an appropriate message.")

    prompt = (
        f"{hint}\n\n"
        f"Recipient: {recipient}\n"
        f"What to say: {intent}\n"
        + (f"Additional context: {context}\n" if context else "") +
        "\nWrite only the message content, nothing else."
    )

    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.message.content or ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()


def _apply_edit(current_message: str, edit_instruction: str, platform: str) -> str:
    """Apply a voice edit instruction to the current draft."""
    prompt = (
        f"Here is a {platform} message draft:\n\n{current_message}\n\n"
        f"Edit instruction: {edit_instruction}\n\n"
        "Rewrite the message applying the edit. Return only the message, nothing else."
    )
    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.message.content or ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()


def _speak(text: str):
    if _speaker:
        _speaker.speak(text)
    else:
        print(f"[Jarvis] {text}")


def _listen() -> str:
    if _listen_fn and _transcribe_fn:
        audio = _listen_fn(verbose=False)
        return _transcribe_fn(audio) if audio else ""
    return input("You: ").strip()


# ── Approval loop ─────────────────────────────────────────────────────────────

SEND_WORDS   = ["send", "yes", "confirm", "go", "do it", "send it"]
CANCEL_WORDS = ["cancel", "no", "stop", "forget it", "never mind", "abort"]
EDIT_WORDS   = ["edit", "change", "make", "rewrite", "fix", "update", "more", "less"]


def _parse_intent(text: str) -> str:
    """Returns 'send', 'cancel', or 'edit'."""
    t = text.lower()
    if any(w in t for w in SEND_WORDS):
        return "send"
    if any(w in t for w in CANCEL_WORDS):
        return "cancel"
    return "edit"   # default — treat anything else as edit instruction


def _read_message_aloud(platform: str, message: str):
    """Read the drafted message aloud in a natural way."""
    if platform.lower() == "gmail":
        # Parse subject and body
        lines = message.strip().splitlines()
        subject, body = "", message
        if lines and lines[0].lower().startswith("subject:"):
            subject = lines[0][8:].strip()
            body    = "\n".join(lines[1:]).strip()

        if subject:
            _speak(f"Subject: {subject}. Message: {body}")
        else:
            _speak(message)
    else:
        _speak(message)


# ── Main compose + approve flow ───────────────────────────────────────────────

def compose_and_approve(
    platform: str,
    recipient: str,
    intent: str,
    context: str = "",
) -> dict:
    """
    Draft a message, read it aloud, loop until user approves or cancels.

    Returns:
        {"status": "approved", "platform": ..., "recipient": ..., "message": ...}
        {"status": "cancelled"}
    """
    _speak(f"Writing your {platform} message to {recipient}...")
    message = _draft(platform, recipient, intent, context)

    for attempt in range(5):   # max 5 edit rounds
        _speak("Here's what I have:")
        _read_message_aloud(platform, message)
        _speak("Send it, edit it, or cancel?")

        response = _listen()
        if not response:
            _speak("Didn't catch that. Send it, edit it, or cancel?")
            continue

        intent_parsed = _parse_intent(response)

        if intent_parsed == "send":
            return {
                "status":    "approved",
                "platform":  platform,
                "recipient": recipient,
                "message":   message,
            }

        elif intent_parsed == "cancel":
            _speak("Message cancelled.")
            return {"status": "cancelled"}

        else:
            # Treat response as edit instruction
            _speak("Updating the message...")
            message = _apply_edit(message, response, platform)

    _speak("Too many edits. Message cancelled.")
    return {"status": "cancelled"}


# ── Senders ───────────────────────────────────────────────────────────────────

def send_gmail(recipient: str, message: str) -> str:
    """Send an email via Gmail API."""
    import base64
    from email.mime.text import MIMEText
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    SCOPES         = ["https://www.googleapis.com/auth/gmail.send"]
    CREDENTIALS    = _REPO_ROOT / "credentials.json"
    TOKEN_FILE     = _REPO_ROOT / "token_gmail_send.json"

    # Parse subject/body
    lines   = message.strip().splitlines()
    subject = "Message from Jarvis"
    body    = message
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0][8:].strip()
        body    = "\n".join(lines[1:]).strip()

    try:
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow  = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds)
        mime    = MIMEText(body)
        mime["to"]      = recipient
        mime["subject"] = subject
        raw     = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {recipient}."

    except Exception as e:
        return f"Failed to send email: {e}"


def send_gchat(recipient: str, message: str) -> str:
    """
    Send a Google Chat message.
    recipient should be a space/room webhook URL or a user email.
    For direct messages, requires Chat API with user auth.
    """
    # Google Chat direct messages via API require domain-level setup.
    # For personal use, easiest is a webhook URL as recipient.
    import urllib.request
    import json

    if recipient.startswith("https://chat.googleapis.com"):
        # Webhook
        try:
            payload = json.dumps({"text": message}).encode()
            req = urllib.request.Request(
                recipient,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8):
                pass
            return "Google Chat message sent."
        except Exception as e:
            return f"Failed to send Google Chat message: {e}"
    else:
        return (
            "Google Chat direct messages require a webhook URL as recipient.\n"
            "Go to your Chat space → Apps & integrations → Webhooks → copy the URL.\n"
            "Then say: 'Send a chat message to <webhook_url>'"
        )


def send_whatsapp(recipient: str, message: str) -> str:
    """
    Send a WhatsApp message via browser automation (WhatsApp Web).
    recipient: phone number with country code (e.g. +1234567890) or contact name.
    Requires Chrome and the user to be logged into WhatsApp Web.
    pip install selenium webdriver-manager
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        import time
        import urllib.parse

        # Encode message for URL
        encoded = urllib.parse.quote(message)
        # Strip non-numeric from phone number
        phone = re.sub(r'[^\d+]', '', recipient)

        url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded}"

        options = Options()
        options.add_argument("--user-data-dir=/tmp/whatsapp-chrome-profile")  # persist login
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )

        driver.get(url)
        wait = WebDriverWait(driver, 30)

        # Wait for send button
        send_btn = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, '//button[@aria-label="Send"]')
            )
        )
        time.sleep(1)   # brief pause so message field is populated
        send_btn.click()
        time.sleep(2)   # wait for send to complete
        driver.quit()

        return f"WhatsApp message sent to {recipient}."

    except ImportError:
        return (
            "selenium and webdriver-manager are required for WhatsApp.\n"
            "Run: pip install selenium webdriver-manager"
        )
    except Exception as e:
        return f"Failed to send WhatsApp message: {e}"


# ── Main entry point called by brain ─────────────────────────────────────────

def compose_message(platform: str, recipient: str, intent: str, context: str = "") -> str:
    """
    Full compose → approve → send flow.
    Called as a tool by the brain.
    Returns a status string for the LLM to report back.
    """
    result = compose_and_approve(platform, recipient, intent, context)

    if result["status"] == "cancelled":
        return "Message cancelled by user."

    platform_l = platform.lower()
    msg        = result["message"]
    rcpt       = result["recipient"]

    if platform_l == "gmail":
        return send_gmail(rcpt, msg)
    elif platform_l in ("google chat", "gchat", "chat"):
        return send_gchat(rcpt, msg)
    elif platform_l == "whatsapp":
        return send_whatsapp(rcpt, msg)
    else:
        return f"Platform '{platform}' is not supported yet."