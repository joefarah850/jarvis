"""
Google Calendar tool — fetches upcoming events via Google Calendar API.
Requires credentials.json in repo root (OAuth 2.0 Desktop app).
"""
from pathlib import Path
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES           = ["https://www.googleapis.com/auth/calendar.readonly"]
_REPO_ROOT       = Path(__file__).parent.parent.parent
CREDENTIALS_FILE = _REPO_ROOT / "credentials.json"
TOKEN_FILE       = _REPO_ROOT / "token_calendar.json"


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

    return build("calendar", "v3", credentials=creds)


def get_calendar_events(days_ahead: int = 7) -> str:
    try:
        service  = _get_service()
        now      = datetime.now(timezone.utc)
        end_time = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

        # Add days_ahead days
        from datetime import timedelta
        end_time = now + timedelta(days=days_ahead)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end_time.isoformat(),
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        if not events:
            return f"No events in the next {days_ahead} days."

        lines = []
        for e in events:
            start    = e["start"].get("dateTime", e["start"].get("date", ""))
            end      = e["end"].get("dateTime", e["end"].get("date", ""))
            summary  = e.get("summary", "(no title)")
            location = e.get("location", "")
            
            # Format datetime nicely
            try:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                start_fmt = dt.strftime("%a %b %d, %I:%M %p")
            except Exception:
                start_fmt = start

            line = f"• {start_fmt} — {summary}"
            if location:
                line += f" @ {location}"
            lines.append(line)

        return f"Upcoming events ({days_ahead} days):\n" + "\n".join(lines)

    except Exception as e:
        return f"Calendar error: {e}"