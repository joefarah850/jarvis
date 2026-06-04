"""
Gmail tool — reads emails via Google Gmail API.
Requires credentials.json in repo root (OAuth 2.0 Desktop app).
"""
import base64
import re
import urllib.request
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES           = ["https://www.googleapis.com/auth/gmail.readonly"]
_REPO_ROOT       = Path(__file__).parent.parent.parent
CREDENTIALS_FILE = _REPO_ROOT / "credentials.json"
TOKEN_FILE       = _REPO_ROOT / "token_gmail.json"

_last_emails: list[dict] = []


def _get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _resolve_netflix_ids(html: str) -> dict[str, str]:
    ids = list(dict.fromkeys(re.findall(r'netflix\.com/title/(\d+)', html)))
    titles = {}
    for nid in ids[:6]:
        try:
            url = f"https://www.netflix.com/oembed?url=https://www.netflix.com/title/{nid}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read())
            titles[nid] = data.get("title")
        except Exception:
            titles[nid] = None
    return titles


def _strip_html(html: str) -> str:
    """Convert HTML to clean readable plain text — no URLs, proper bullets."""
    # Resolve Netflix title IDs to show names
    netflix_titles = _resolve_netflix_ids(html)
    def replace_netflix(m):
        t = netflix_titles.get(m.group(1))
        return t if t else ""
    html = re.sub(r'https?://(?:www\.)?netflix\.com/title/(\d+)[^\s"\'<>]*', replace_netflix, html)

    # Drop style/script
    html = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Preserve img alt text
    html = re.sub(r'<img[^>]+alt=["\']([^"\']{3,})["\'][^>]*>', r' \1 ', html, flags=re.IGNORECASE)
    # List items → bullets
    html = re.sub(r'<li[^>]*>', '\n- ', html, flags=re.IGNORECASE)
    # Block elements → newlines
    html = re.sub(r'<(br|p|div|tr|h\d|td)[^>]*>', '\n', html, flags=re.IGNORECASE)
    # Strip all remaining tags
    html = re.sub(r'<[^>]+>', '', html)
    # Decode entities
    for ent, char in [('&nbsp;',' '),('&amp;','&'),('&lt;','<'),('&gt;','>'),('&#39;',"'"),('&quot;','"')]:
        html = html.replace(ent, char)
    # Remove all URLs
    html = re.sub(r'https?://\S+', '', html)
    # Clean up
    html = re.sub(r'\[\s*\]', '', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    html = re.sub(r'[ \t]+', ' ', html)
    lines = [l.strip() for l in html.splitlines() if l.strip()]
    return '\n'.join(lines)


def _extract_part(payload: dict, mime_type: str) -> str:
    if payload.get("mimeType") == mime_type:
        data = payload.get("body", {}).get("data", "")
        if data:
            try:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
            except Exception:
                return ""
    if payload.get("mimeType", "").startswith("multipart/"):
        for part in payload.get("parts", []):
            result = _extract_part(part, mime_type)
            if result and result.strip():
                return result
    return ""


def _extract_body(payload: dict) -> str:
    plain = _extract_part(payload, "text/plain")
    if plain and len(plain.strip()) > 50:
        plain = re.sub(r'https?://\S+', '', plain)
        return plain.strip()
    html = _extract_part(payload, "text/html")
    if html:
        return _strip_html(html)
    return ""


def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _sender_name(from_header: str) -> str:
    match = re.match(r'^"?([^"<]+)"?\s*<', from_header)
    if match:
        return match.group(1).strip()
    return from_header.split("@")[0]


def read_emails(max_results: int = 5, unread_only: bool = False) -> str:
    global _last_emails
    try:
        service = _get_service()
        query   = "is:unread" if unread_only else ""

        result = service.users().messages().list(
            userId="me", maxResults=max_results, q=query
        ).execute()

        messages = result.get("messages", [])
        if not messages:
            return "No emails found."

        _last_emails = []
        summaries    = []

        for m in messages:
            msg     = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
            headers = msg["payload"].get("headers", [])
            subject = _get_header(headers, "Subject") or "(no subject)"
            sender  = _get_header(headers, "From")
            date    = _get_header(headers, "Date")
            body    = _extract_body(msg["payload"])
            snippet = re.sub(r'https?://\S+', '', msg.get("snippet", ""))
            content = (body or snippet)[:3000]

            sender_name = _sender_name(sender)
            _last_emails.append({
                "from": sender, "sender": sender_name,
                "date": date, "subject": subject, "content": content,
            })

            # Original format the LLM handles well
            summaries.append(
                f"From: {sender_name}\n"
                f"Date: {date}\n"
                f"Subject: {subject}\n"
                f"Content: {content[:2000]}"
            )

        return "\n\n---\n\n".join(summaries)

    except Exception as e:
        return f"Email error: {e}"


def get_cached_emails() -> list[dict]:
    return _last_emails