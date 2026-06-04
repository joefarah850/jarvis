"""
Web search via DuckDuckGo — no API key needed.
pip install ddgs
"""
from ddgs import DDGS
from datetime import datetime

_ddgs = DDGS()


def web_search(query: str, max_results: int = 5) -> str:
    try:
        now = datetime.now()
        current_year = now.year
        current_date = now.strftime("%B %d %Y")

        if str(current_year) not in query:
            query = f"{query} {current_year}"

        results = list(_ddgs.text(query, max_results=max_results, timelimit="m"))
        if not results:
            results = list(_ddgs.text(query, max_results=max_results))

        if not results:
            return f"No results found for: {query}"

        lines = [f"Search date: {current_date}"]
        for r in results:
            title = r.get("title", "")
            body  = r.get("body", "")[:200]
            url   = r.get("href", "")
            date  = r.get("date", "")
            date_str = f" [{date}]" if date else ""
            # Always include URL so LLM can fetch_page if snippets are insufficient
            lines.append(f"• {title}{date_str}\n  URL: {url}\n  {body}")

        lines.append("\nIf snippets are too short, call fetch_page on the most relevant URL above.")
        return "\n".join(lines)

    except Exception as e:
        return f"Search failed: {e}"


def fetch_page(url: str, max_chars: int = 4000) -> str:
    """
    Fetch the full text content of a URL.
    Use after web_search when snippets are too short to answer the question.
    """
    import urllib.request
    import re

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        html = re.sub(r'<(script|style|nav|footer|header)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<li[^>]*>', '\n- ', html, flags=re.IGNORECASE)
        html = re.sub(r'<(br|p|div|tr|h\d|td|th)[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<[^>]+>', '', html)
        for ent, char in [('&nbsp;', ' '), ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&#39;', "'")]:
            html = html.replace(ent, char)
        html = re.sub(r'https?://\S+', '', html)
        html = re.sub(r'\n{3,}', '\n\n', html)
        html = re.sub(r'[ \t]+', ' ', html)
        lines = [l.strip() for l in html.splitlines() if l.strip()]
        text = '\n'.join(lines)
        return text[:max_chars]

    except Exception as e:
        return f"Failed to fetch {url}: {e}"