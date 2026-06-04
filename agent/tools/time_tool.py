"""
Time tool — converts local system time to any timezone.
No web search needed, uses the system clock directly.
pip install pytz
"""
from datetime import datetime
import pytz


# Common city/country → timezone mappings for natural language
TIMEZONE_MAP = {
    # North America
    "montreal": "America/Montreal",
    "toronto": "America/Toronto",
    "new york": "America/New_York",
    "new york city": "America/New_York",
    "nyc": "America/New_York",
    "eastern": "America/New_York",
    "chicago": "America/Chicago",
    "central": "America/Chicago",
    "denver": "America/Denver",
    "mountain": "America/Denver",
    "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "pacific": "America/Los_Angeles",
    "vancouver": "America/Vancouver",
    "mexico city": "America/Mexico_City",
    "canada": "America/Toronto",
    "usa": "America/New_York",
    "us": "America/New_York",

    # Europe
    "london": "Europe/London",
    "uk": "Europe/London",
    "paris": "Europe/Paris",
    "france": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "germany": "Europe/Berlin",
    "madrid": "Europe/Madrid",
    "spain": "Europe/Madrid",
    "rome": "Europe/Rome",
    "italy": "Europe/Rome",
    "amsterdam": "Europe/Amsterdam",
    "beirut": "Asia/Beirut",
    "lebanon": "Asia/Beirut",
    "istanbul": "Europe/Istanbul",
    "turkey": "Europe/Istanbul",
    "moscow": "Europe/Moscow",
    "russia": "Europe/Moscow",

    # Asia
    "dubai": "Asia/Dubai",
    "uae": "Asia/Dubai",
    "riyadh": "Asia/Riyadh",
    "saudi": "Asia/Riyadh",
    "india": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata",
    "singapore": "Asia/Singapore",
    "hong kong": "Asia/Hong_Kong",
    "shanghai": "Asia/Shanghai",
    "beijing": "Asia/Shanghai",
    "china": "Asia/Shanghai",
    "tokyo": "Asia/Tokyo",
    "japan": "Asia/Tokyo",
    "seoul": "Asia/Seoul",
    "korea": "Asia/Seoul",

    # Oceania
    "sydney": "Australia/Sydney",
    "australia": "Australia/Sydney",
    "melbourne": "Australia/Melbourne",
    "auckland": "Pacific/Auckland",
    "new zealand": "Pacific/Auckland",
}


def get_time(location: str = "local") -> str:
    """
    Get the current time in any city or timezone.
    Uses the system clock — no web search needed, always accurate.
    """
    try:
        now_utc = datetime.now(pytz.utc)

        if location.lower() in ("local", "here", ""):
            now_local = datetime.now()
            return f"Local time: {now_local.strftime('%I:%M %p, %A %B %d %Y')}"

        # Look up timezone
        loc_key = location.lower().strip()
        tz_name = TIMEZONE_MAP.get(loc_key)

        # Try partial match if exact not found
        if not tz_name:
            for key, tz in TIMEZONE_MAP.items():
                if loc_key in key or key in loc_key:
                    tz_name = tz
                    break

        # Try treating the input as a direct pytz timezone name
        if not tz_name:
            try:
                pytz.timezone(location)
                tz_name = location
            except pytz.UnknownTimeZoneError:
                return (
                    f"Unknown location: '{location}'.\n"
                    f"Try a major city name (e.g. 'Tokyo', 'London', 'New York')."
                )

        tz      = pytz.timezone(tz_name)
        now_tz  = now_utc.astimezone(tz)
        offset  = now_tz.strftime('%z')
        offset_str = f"UTC{offset[:3]}:{offset[3:]}"

        return (
            f"Current time in {location.title()}: "
            f"{now_tz.strftime('%I:%M %p, %A %B %d %Y')} "
            f"({offset_str})"
        )

    except Exception as e:
        return f"Time lookup error: {e}"