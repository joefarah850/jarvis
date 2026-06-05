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


def _clean_name(name: str) -> str:
    """Strip emojis, special chars and extra whitespace from a contact name."""
    import unicodedata
    cleaned = []
    for ch in name:
        cat = unicodedata.category(ch)
        # Keep letters, numbers, spaces, hyphens, apostrophes
        if cat.startswith(('L', 'N')) or ch in (" ", "-", "'", "."):
            cleaned.append(ch)
    return " ".join("".join(cleaned).split())   # collapse whitespace


def _fuzzy_score(spoken: str, name: str) -> float:
    """
    Score how well a spoken string matches a contact name.
    Uses multiple strategies to handle speech recognition errors,
    especially for non-English names.
    """
    spoken = _clean_name(spoken).lower().strip()
    name   = _clean_name(name).lower().strip()

    if spoken == name:
        return 1.0

    # Exact substring
    if spoken in name or name in spoken:
        return 0.9

    # Word-level match — each spoken word compared to each name word
    spoken_words = spoken.split()
    name_words   = name.split()
    word_scores  = []
    for sw in spoken_words:
        best = max(
            (_char_similarity(sw, nw) for nw in name_words),
            default=0.0
        )
        word_scores.append(best)

    if word_scores:
        # Average word match, boosted if first word matches well (first name)
        avg = sum(word_scores) / len(word_scores)
        first_boost = word_scores[0] * 0.1 if word_scores else 0
        return min(avg + first_boost, 1.0)

    return _char_similarity(spoken, name)


def _char_similarity(a: str, b: str) -> float:
    """Character-level similarity (simplified Jaro-like)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # Count common characters within a window
    window  = max(len(a), len(b)) // 2 - 1
    a_match = [False] * len(a)
    b_match = [False] * len(b)
    matches = 0

    for i, ca in enumerate(a):
        start = max(0, i - window)
        end   = min(i + window + 1, len(b))
        for j in range(start, end):
            if not b_match[j] and ca == b[j]:
                a_match[i] = True
                b_match[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    # Transpositions
    t = 0
    k = 0
    for i in range(len(a)):
        if a_match[i]:
            while not b_match[k]:
                k += 1
            if a[i] != b[k]:
                t += 1
            k += 1

    jaro = (matches/len(a) + matches/len(b) + (matches - t/2)/matches) / 3

    # Jaro-Winkler prefix boost
    prefix = 0
    for i in range(min(4, min(len(a), len(b)))):
        if a[i] == b[i]:
            prefix += 1
        else:
            break
    return jaro + prefix * 0.1 * (1 - jaro)
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
        f"You are Jarvis, an AI voice assistant. Your name is Jarvis.\n"
        f"When introducing yourself, explain that you are an AI assistant called Jarvis "
        f"that can help with tasks like reading emails, managing calendars, searching the web, "
        f"sending messages, setting reminders, and more.\n"
        f"IMPORTANT: Do NOT use emojis — they cause technical issues when sending.\n\n"
        f"Recipient: {recipient}\n"
        f"What to say: {intent}\n"
        + (f"Additional context: {context}\n" if context else "") +
        "\nWrite only the message content, nothing else. No emojis."
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

SEND_WORDS   = ["send", "yes", "confirm", "go", "do it", "send it", "sned", "yep", "yeah", "ok", "okay", "sure", "absolutely", "perfect", "great"]
# Cancel words only when they appear alone or with "it/the message" — not mid-sentence edit instructions
CANCEL_PHRASES = ["cancel", "cancel it", "cancel the message", "no don't send", "forget it", "never mind", "abort", "don't send"]
EDIT_WORDS     = ["edit", "change", "make", "rewrite", "fix", "update", "more", "less",
                  "remove", "add", "replace", "instead", "don't say", "without", "shorten",
                  "longer", "shorter", "formal", "casual", "tone", "rephrase"]


def _parse_intent(text: str) -> str:
    """Returns 'send', 'cancel', or 'edit'."""
    t    = text.lower().strip()
    tlen = len(t.split())

    # Send — short clear confirmations
    if any(t == w or t.startswith(w + " ") for w in ["send", "yes", "yep", "yeah", "ok", "okay",
                                                        "sure", "go", "perfect", "great", "sned"]):
        return "send"
    if any(w in t for w in ["send it", "do it", "confirm", "absolutely"]):
        return "send"

    # Cancel — only exact phrases, not mid-sentence
    if any(t == p or t == p + "." for p in CANCEL_PHRASES):
        return "cancel"
    # "no" alone = cancel, but "no, remove X" = edit
    if t in ("no", "no.", "nope", "nope.") and tlen <= 2:
        return "cancel"

    # Edit — if it contains edit words and is longer than a simple command
    if any(w in t for w in EDIT_WORDS):
        return "edit"

    # Default: if it's a longer sentence it's probably an edit instruction
    if tlen > 3:
        return "edit"

    return "cancel"


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


def _resolve_gchat_recipient(recipient: str) -> str:
    """
    Resolve a spoken name ('dev team') to a webhook URL.
    Falls back to the recipient as-is if it's already a URL.
    """
    if recipient.startswith("https://"):
        return recipient

    webhooks_file = _REPO_ROOT / "gchat_webhooks.json"
    if not webhooks_file.exists():
        return ""

    import json
    with open(webhooks_file, encoding="utf-8") as f:
        webhooks = json.load(f)

    # Remove comment key
    webhooks = {k: v for k, v in webhooks.items() if not k.startswith("_")}

    # Exact match first
    recipient_l = recipient.lower().strip()
    if recipient_l in webhooks:
        return webhooks[recipient_l]

    # Fuzzy match — find best partial overlap
    best_match = None
    best_score = 0
    for name, url in webhooks.items():
        words = set(name.lower().split())
        spoken = set(recipient_l.split())
        overlap = len(words & spoken) / max(len(words), 1)
        if overlap > best_score and overlap > 0.5:
            best_score = overlap
            best_match = url

    return best_match or ""


def send_gchat(recipient: str, message: str) -> str:
    """
    Send a Google Chat message.
    - If recipient matches a webhook shortcut → sends via webhook (for Spaces)
    - Otherwise → resolves email from contacts then sends DM via browser automation
    """
    import urllib.request
    import json

    url = _resolve_gchat_recipient(recipient)

    if url:
        # Webhook path (Spaces)
        try:
            payload = json.dumps({"text": message}).encode()
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8):
                pass
            return f"Google Chat message sent to {recipient}."
        except Exception as e:
            return f"Failed to send Google Chat webhook message: {e}"

    # DM path — resolve contact email first
    resolved = _resolve_gchat_contact(recipient)
    return _send_gchat_dm(resolved, message)


def _resolve_gchat_contact(recipient: str) -> str:
    """
    Resolve a contact name to an email for Google Chat DM.
    Checks gchat_contacts.json first, then looks up Google Contacts.
    """
    import json

    # Already looks like an email
    if "@" in recipient:
        return recipient

    contacts_file = _REPO_ROOT / "gchat_contacts.json"
    contacts = {}
    if contacts_file.exists():
        with open(contacts_file, encoding="utf-8") as f:
            contacts = {k: v for k, v in json.load(f).items() if not k.startswith("_")}

    recipient_l = _clean_name(recipient).lower().strip()

    # Exact match
    if recipient_l in contacts:
        return contacts[recipient_l]

    # Fuzzy match using Jaro-Winkler similarity
    best_name, best_score = None, 0.0
    for name, email in contacts.items():
        score = _fuzzy_score(recipient_l, name.lower())
        if score > best_score:
            best_score = score
            best_name  = name
    if best_score >= 0.75 and best_name:
        return contacts[best_name]

    # Auto-lookup from Google Contacts
    result = lookup_contact_email(recipient)
    if "Saved to contacts" in result:
        with open(contacts_file, encoding="utf-8") as f:
            contacts = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        if recipient_l in contacts:
            return contacts[recipient_l]

    return recipient   # fall back to using name as-is in search


def _send_gchat_dm(recipient: str, message: str) -> str:
    """
    Send a Google Chat DM via the Chat API.
    recipient: email address of the person to DM.
    Requires chat.googleapis.com People API scope.
    """
    from pathlib import Path
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    SCOPES     = [
        "https://www.googleapis.com/auth/chat.messages.create",
        "https://www.googleapis.com/auth/chat.spaces.create",
    ]
    CREDS_FILE = _REPO_ROOT / "credentials.json"
    TOKEN_FILE = _REPO_ROOT / "token_gchat_dm.json"

    try:
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        service = build("chat", "v1", credentials=creds)

        # Step 1: Find or create a DM space with the recipient
        dm_space = service.spaces().findDirectMessage(
            name=f"users/{recipient}"
        ).execute()

        space_name = dm_space.get("name")
        if not space_name:
            # Create DM space
            dm_space = service.spaces().create(
                body={
                    "spaceType": "DIRECT_MESSAGE",
                    "singleUserBotDm": False,
                }
            ).execute()
            space_name = dm_space.get("name")

        # Step 2: Send the message
        service.spaces().messages().create(
            parent=space_name,
            body={"text": message},
        ).execute()

        return f"Google Chat DM sent to {recipient}."

    except Exception as e:
        err = str(e)
        if "PERMISSION_DENIED" in err or "403" in err:
            return (
                "Permission denied for Google Chat API.\n"
                "In Google Cloud Console:\n"
                "1. Enable the Google Chat API\n"
                "2. Add scopes: chat.messages.create and chat.spaces.create\n"
                "3. Delete token_gchat_dm.json and re-authenticate"
            )
        if "NOT_FOUND" in err or "404" in err:
            return f"Could not find a Google Chat account for {recipient}. Make sure they use Google Workspace."
        return f"Failed to send Google Chat DM: {err}"



def _resolve_whatsapp_contact(recipient: str) -> str:
    """
    Resolve a contact name to a phone number.
    1. Check whatsapp_contacts.json
    2. Auto-lookup from Google Contacts and save result
    Returns phone number string or empty string if not found.
    """
    import json

    # Already a phone number
    phone = re.sub(r"[^\d+]", "", recipient)
    if len(phone) >= 7:
        return phone

    contacts_file = _REPO_ROOT / "whatsapp_contacts.json"
    if not contacts_file.exists():
        return ""

    with open(contacts_file, encoding="utf-8") as f:
        contacts = {k: v for k, v in json.load(f).items() if not k.startswith("_")}

    recipient_l = _clean_name(recipient).lower().strip()

    # Exact match
    if recipient_l in contacts:
        return re.sub(r"[^\d+]", "", contacts[recipient_l])

    # Fuzzy match using Jaro-Winkler similarity
    best_name, best_score = None, 0.0
    for name, number in contacts.items():
        score = _fuzzy_score(recipient_l, name.lower())
        if score > best_score:
            best_score = score
            best_name  = name
    if best_score >= 0.75 and best_name:
        return re.sub(r"[^\d+]", "", contacts[best_name])

    # Not found locally — try Google Contacts
    result = lookup_phone_number(recipient)

    if "Saved to contacts" in result:
        # Single number found and saved — re-read and return it
        with open(contacts_file, encoding="utf-8") as f:
            contacts = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        if recipient_l in contacts:
            return re.sub(r"[^\d+]", "", contacts[recipient_l])

    if "MULTIPLE_NUMBERS:" in result:
        # Return the raw result — brain will parse and ask user to pick
        return f"MULTIPLE:{result}"

    return ""


def send_whatsapp(recipient: str, message: str) -> str:
    """
    Send a WhatsApp message via browser automation (WhatsApp Web).
    Uses wa.me URL method — most reliable approach.
    Resolves contact names via whatsapp_contacts.json.
    pip install selenium webdriver-manager
    """
    import urllib.parse

    # Resolve contact name to phone number
    phone = _resolve_whatsapp_contact(recipient)

    if not phone:
        import json
        # Last resort — tell user what we have and what to do
        contacts_file = _REPO_ROOT / "whatsapp_contacts.json"
        known = []
        if contacts_file.exists():
            known = list({k: v for k, v in json.load(open(contacts_file, encoding="utf-8")).items()
                          if not k.startswith("_")}.keys())
        known_str = ", ".join(f'"{k}"' for k in known) if known else "none"
        return (
            f'Could not find a phone number for "{recipient}" in local contacts or Google Contacts.\n'
            f"Known contacts: {known_str}\n"
            f"Say: 'add WhatsApp contact {recipient} +[number]' to add them manually."
        )

    # Multiple numbers found — ask user to pick
    if phone.startswith("MULTIPLE:"):
        raw = phone.replace("MULTIPLE:", "")
        # Parse: MULTIPLE_NUMBERS:ContactName:label1:num1|label2:num2
        parts     = raw.split("MULTIPLE_NUMBERS:")[1]
        name_part, numbers_raw = parts.split(":", 1)
        entries   = numbers_raw.split("|")
        numbers_list = []
        for entry in entries:
            label, num = entry.rsplit(":", 1)
            numbers_list.append((label, num))

        # Read the choice via voice
        options = "\n".join(f"{i+1}. {label}: {num}" for i, (label, num) in enumerate(numbers_list))
        _speak(f"{name_part} has multiple numbers:\n{options}\nWhich one should I use?")
        response = _listen()

        # Parse user response — look for a number or label
        chosen_phone = None
        response_l   = response.lower()
        for i, (label, num) in enumerate(numbers_list):
            if str(i + 1) in response or label.lower() in response_l:
                chosen_phone = num
                break
        if not chosen_phone:
            chosen_phone = numbers_list[0][1]   # default to first

        # Save chosen number
        import json
        contacts_file = _REPO_ROOT / "whatsapp_contacts.json"
        contacts = {}
        if contacts_file.exists():
            with open(contacts_file, encoding="utf-8") as f:
                contacts = json.load(f)
        contacts[recipient.lower()] = chosen_phone
        with open(contacts_file, "w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=2)

        phone = chosen_phone

    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        import time

        profile_dir = str(_REPO_ROOT / ".chrome-whatsapp-profile")
        encoded     = urllib.parse.quote(message)
        url         = f"https://web.whatsapp.com/send?phone={phone}&text={encoded}"

        options = Options()
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )
        wait = WebDriverWait(driver, 45)

        driver.get(url)

        # Wait for send button — message is pre-filled via URL
        send_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH,
                '//button[@aria-label="Send"] | '
                '//span[@data-icon="send"]/parent::button | '
                '//div[@aria-label="Send"]'
            ))
        )
        time.sleep(1)
        send_btn.click()
        time.sleep(2)
        driver.quit()
        return f"WhatsApp message sent to {recipient}."

    except ImportError:
        return "selenium and webdriver-manager are required. Run: pip install selenium webdriver-manager"
    except Exception as e:
        try:
            driver.quit()
        except Exception:
            pass
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


def lookup_contact_email(name: str) -> str:
    """
    Look up a contact email from Google Contacts by name.
    Saves result to gchat_contacts.json for future use.
    """
    import json
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    SCOPES     = ["https://www.googleapis.com/auth/contacts.readonly"]
    CREDS_FILE = _REPO_ROOT / "credentials.json"
    TOKEN_FILE = _REPO_ROOT / "token_contacts.json"

    name = _clean_name(name)   # strip emojis before API call

    try:
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        service = build("people", "v1", credentials=creds)
        results = service.people().searchContacts(
            query=name,
            readMask="names,emailAddresses",
            pageSize=10,
        ).execute()

        matches = results.get("results", [])
        if not matches:
            return f'No Google Contact found for "{name}". Try using their full name.'

        # Find best fuzzy match — must score above 0.7 to avoid wrong person
        best_match, best_score = None, 0.0
        for m in matches:
            p = m.get("person", {})
            display = p.get("names", [{}])[0].get("displayName", "")
            score = _fuzzy_score(name, display)
            if score > best_score:
                best_score = score
                best_match = m

        if not best_match or best_score < 0.7:
            return f'No confident match found for "{name}". Best guess was score {best_score:.2f}. Try using their full name.'

        person       = best_match.get("person", {})
        names        = person.get("names", [])
        emails       = person.get("emailAddresses", [])
        contact_name = names[0].get("displayName", name) if names else name

        if not emails:
            return f'Found "{contact_name}" but no email address is saved for them.'

        # Prefer work/primary email
        email = None
        for e in emails:
            t = e.get("type", "").lower()
            if "work" in t or "primary" in t:
                email = e.get("value", "")
                break
        if not email:
            email = emails[0].get("value", "")

        # Save to gchat_contacts.json
        contacts_file = _REPO_ROOT / "gchat_contacts.json"
        contacts = {}
        if contacts_file.exists():
            with open(contacts_file, encoding="utf-8") as f:
                contacts = json.load(f)
        contacts[name.lower()] = email
        with open(contacts_file, "w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=2)

        return f'Found {contact_name}: {email}. Saved to contacts.'

    except Exception as e:
        return f"Failed to look up contact email: {e}"


def add_gchat_webhook(name: str, url: str) -> str:
    """Add or update a Google Chat webhook shortcut."""
    import json
    webhooks_file = _REPO_ROOT / "gchat_webhooks.json"
    webhooks = {}
    if webhooks_file.exists():
        with open(webhooks_file, encoding="utf-8") as f:
            webhooks = json.load(f)
    webhooks[name.lower()] = url
    with open(webhooks_file, "w", encoding="utf-8") as f:
        json.dump(webhooks, f, indent=2)
    return f"Saved Google Chat shortcut: \"{name}\""


def list_gchat_webhooks() -> str:
    """List all saved Google Chat webhook shortcuts."""
    import json
    webhooks_file = _REPO_ROOT / "gchat_webhooks.json"
    if not webhooks_file.exists():
        return "No Google Chat webhooks configured yet."
    with open(webhooks_file, encoding="utf-8") as f:
        webhooks = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    if not webhooks:
        return "No Google Chat webhooks configured yet."
    return "Google Chat shortcuts:\n" + "\n".join(f"- {k}" for k in webhooks)


def lookup_phone_number(name: str) -> str:
    """
    Look up a phone number from Google Contacts.
    Saves the result to whatsapp_contacts.json automatically.
    """
    import json
    from pathlib import Path
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    SCOPES     = ["https://www.googleapis.com/auth/contacts.readonly"]
    CREDS_FILE = _REPO_ROOT / "credentials.json"
    TOKEN_FILE = _REPO_ROOT / "token_contacts.json"

    try:
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        service = build("people", "v1", credentials=creds)

        # Search Google Contacts
        results = service.people().searchContacts(
            query=_clean_name(name),
            readMask="names,phoneNumbers",
            pageSize=10,
        ).execute()

        matches = results.get("results", [])
        if not matches:
            return f'No Google Contact found for "{name}". Try using their full name.'

        # Find best fuzzy match — must score above 0.7 to avoid wrong person
        best_match, best_score = None, 0.0
        for m in matches:
            p = m.get("person", {})
            display = p.get("names", [{}])[0].get("displayName", "")
            score = _fuzzy_score(name, display)
            if score > best_score:
                best_score = score
                best_match = m

        if not best_match or best_score < 0.7:
            return f'No confident match found for "{name}". Best guess was score {best_score:.2f}. Try using their full name.'

        person   = best_match.get("person", {})
        names    = person.get("names", [])
        phones   = person.get("phoneNumbers", [])
        contact_name = names[0].get("displayName", name) if names else name

        if not phones:
            return f'Found "{contact_name}" in Google Contacts but no phone number is saved for them.'

        # Clean and label all numbers
        clean_phones = []
        for p in phones:
            number = re.sub(r"[^\d+]", "", p.get("value", ""))
            label  = p.get("formattedType", p.get("type", "phone"))
            if number:
                clean_phones.append((label, number))

        if not clean_phones:
            return f'Found "{contact_name}" but could not parse their phone number.'

        if len(clean_phones) == 1:
            # Only one number — use it directly
            label, phone_clean = clean_phones[0]
        else:
            # Multiple numbers — return them all so the brain can ask the user
            numbers_str = "\n".join(f"{i+1}. {label}: {num}" for i, (label, num) in enumerate(clean_phones))
            return (
                f'Found {contact_name} with multiple numbers:\n{numbers_str}\n'
                f"MULTIPLE_NUMBERS:{contact_name}:" + "|".join(f"{l}:{n}" for l, n in clean_phones)
            )

        # Auto-save to whatsapp_contacts.json
        contacts_file = _REPO_ROOT / "whatsapp_contacts.json"
        contacts = {}
        if contacts_file.exists():
            with open(contacts_file, encoding="utf-8") as f:
                contacts = json.load(f)
        contacts[name.lower()] = phone_clean
        with open(contacts_file, "w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=2)

        return f'Found {contact_name}: {phone_clean}. Saved to contacts.'

    except Exception as e:
        return f"Failed to look up contact: {e}"


def add_whatsapp_contact(name: str, phone: str = "") -> str:
    """
    Add or update a WhatsApp contact.
    If phone is not provided, auto-looks up from Google Contacts.
    """
    import json

    clean = _clean_name(name)

    # No phone provided — look up from Google Contacts
    if not phone:
        result = lookup_phone_number(clean)
        if "Saved to contacts" in result:
            return result   # already saved by lookup_phone_number
        if "MULTIPLE_NUMBERS" in result:
            return result   # will be handled by send_whatsapp flow
        return (
            f'Could not find a phone number for "{name}" in Google Contacts.\n'
            f"Please provide the number: 'add WhatsApp contact {name} +1234567890'"
        )

    contacts_file = _REPO_ROOT / "whatsapp_contacts.json"
    contacts = {}
    if contacts_file.exists():
        with open(contacts_file, encoding="utf-8") as f:
            contacts = json.load(f)
    contacts[clean.lower()] = phone
    with open(contacts_file, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2)
    return f'Saved WhatsApp contact: "{name}" → {phone}'


def list_whatsapp_contacts() -> str:
    """List all saved WhatsApp contacts."""
    import json
    contacts_file = _REPO_ROOT / "whatsapp_contacts.json"
    if not contacts_file.exists():
        return "No WhatsApp contacts saved yet."
    with open(contacts_file, encoding="utf-8") as f:
        contacts = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    if not contacts:
        return "No WhatsApp contacts saved yet."
    return "WhatsApp contacts:\n" + "\n".join(f"- {k}: {v}" for k, v in contacts.items())