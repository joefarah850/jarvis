import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OLLAMA_MODEL, OLLAMA_BASE_URL
from ollama import Client

client = Client(host=OLLAMA_BASE_URL)

def _get_name() -> str:
    """Get the assistant name from config."""
    try:
        from config import ASSISTANT_NAME
        return ASSISTANT_NAME
    except Exception:
        return "Jarvis"

SYSTEM_PROMPT_TEMPLATE = """/no_think
You are {assistant_name}. Your name is {assistant_name}. When composing messages on behalf of the user, sign off as {assistant_name} or introduce yourself as {assistant_name} — never as "[Your Name]" or "[Name]".
Current date and time: {datetime_now}. Always use this exact date when searching for current events, standings, news, or time. Never assume a date or use older years.
You are {assistant_name}, a sharp and efficient AI assistant. Short, confident sentences. No filler. No markdown headers. No emojis.

Tool selection rules:
- For TIME questions ("what time is it in X", "current time in Y"): ALWAYS use get_time, never web_search.
- For WEATHER, NEWS, SPORTS, PRICES, EVENTS: use web_search.
- The user says "currently", "right now", "today", "latest", "who is", "what is the current": use web_search.
- Never say you cannot provide real-time data. Always use a tool.
- Search snippets are often too short. ALWAYS call fetch_page on the most relevant URL before answering — do not answer from snippets alone.
- This is mandatory when the answer involves: scores, opponents, winners, dates, locations, standings, or any specific fact.
- Only answer after fetch_page has returned the full content. If fetch_page fails or returns garbage, try the next URL.
- NEVER state specific details (names, scores, opponents, dates) that are not explicitly present in the fetched page content.

Email rules — when listing emails use ONLY this format and nothing else:
"Here are your N emails:
1. Sender — Subject
2. Sender — Subject"
Do not summarize content unless the user asks.

General rules:
- When the user asks about a specific email, answer in 2-3 sentences from the tool result only.
- After ANY tool completes successfully, respond in ONE short sentence confirming what was done. Then STOP. Do not ask follow-up questions. Do not offer to do more. Do not say "Shall I...", "Would you like...", "Is there anything else...", "Let me know if...", or any similar phrase. Just confirm and stop.
- Never generate links or URLs. Never invent information. Never end with filler like "Let me know if...".
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_emails",
            "description": "Read recent emails from Gmail. Use when the user asks about emails, inbox, or messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Number of emails to fetch (default 5)"},
                    "unread_only": {"type": "boolean", "description": "If true, fetch only unread emails"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar_events",
            "description": "Get upcoming calendar events. Use when user asks about schedule, meetings, or calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "How many days ahead to look (default 7)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": f"Set a one-time or recurring reminder. {_get_name()} will speak it aloud and optionally send a WhatsApp or email notification when it fires.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message":         {"type": "string",  "description": "What to remind the user (e.g. 'Call John', 'Take medication')"},
                    "when":            {"type": "string",  "description": "When to fire: 'in 10 minutes', 'at 3pm', 'tomorrow at 9am'"},
                    "recurrence":      {"type": "string",  "description": "Optional: 'daily', 'weekly', 'hourly', 'weekdays'. Leave empty for one-time."},
                    "notify_whatsapp": {"type": "string",  "description": "Optional phone number or contact name to also send a WhatsApp message"},
                    "notify_email":    {"type": "string",  "description": "Optional email address to also send an email notification"},
                },
                "required": ["message", "when"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List all active reminders.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reminder",
            "description": "Cancel a reminder by its ID number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "integer", "description": "The reminder ID to cancel"},
                },
                "required": ["reminder_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_todos",
            "description": "List all tasks in the todo list. Use when user asks to see, show, or list their tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_done": {"type": "boolean", "description": "If true, also show completed tasks. Default false."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_todo",
            "description": "Mark a todo task as done. Use task_name when the user mentions the task by name, task_id when they give a number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id":   {"type": "integer", "description": "The task ID number to mark as done (optional)"},
                    "task_name": {"type": "string",  "description": "The task name or description to match (optional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_todos",
            "description": "Clear the todo list. Removes all tasks or just completed ones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "completed_only": {"type": "boolean", "description": "If true, only remove completed tasks. If false (default), clear everything."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_todo",
            "description": "Add a task to the to-do list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "The task description"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a file. Always call this before edit_file to get exact text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root (e.g. jarvis/config.py)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Add new lines to the END of an existing file. Use this when the user wants to ADD something to a file (new variables, functions, config entries). NEVER use write_file for existing files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root"},
                    "content": {"type": "string", "description": "Content to add at the end of the file"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace a specific existing piece of text in a file. Use to MODIFY existing lines. Always call read_file first. Never use this to add new content — use append_file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root"},
                    "old_text": {"type": "string", "description": "Exact text currently in the file to replace"},
                    "new_text": {"type": "string", "description": "New text to put in its place"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a BRAND NEW file. Only use for files that do not exist yet. Will refuse if file already exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root"},
                    "content": {"type": "string", "description": "Full content of the new file"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path relative to workspace root (default: workspace root)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_line",
            "description": "Remove all lines containing a specific word or phrase from a file. Use this for DELETE/REMOVE operations — much safer than edit_file for deletions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root"},
                    "containing": {"type": "string", "description": "Substring to match — any line containing this will be removed (e.g. 'anghami')"},
                },
                "required": ["path", "containing"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compose_message",
            "description": "Draft, read aloud, get voice approval, then send a message. Use for Gmail, Google Chat, or WhatsApp. recipient can be a name (e.g. Ahmad), email, or phone number — the tool will resolve it automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["gmail", "google chat", "whatsapp"],
                        "description": "Where to send the message"
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Email address, phone number, or contact name"
                    },
                    "intent": {
                        "type": "string",
                        "description": "What the message should say — summarize the user's intent"
                    },
                    "context": {
                        "type": "string",
                        "description": "Any extra context to help write the message (optional)"
                    },
                },
                "required": ["platform", "recipient", "intent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_contact_email",
            "description": "Look up a contact email address from Google Contacts by name. Use when sending a Google Chat DM and you only have a name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The contact name to look up"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_phone_number",
            "description": "Look up a phone number from Google Contacts by name and save it to WhatsApp contacts. Use when the user wants to send a WhatsApp message but the contact is not saved yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The contact name to look up"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_whatsapp_contact",
            "description": "Save a WhatsApp contact. If only a name is given (no number), auto-looks up from Google Contacts. Use when user says 'add WhatsApp contact [name]' or 'add WhatsApp contact [name] [number]'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":  {"type": "string", "description": "Contact name (e.g. 'emile', 'mom')"},
                    "phone": {"type": "string", "description": "Phone number with country code (optional — leave empty to auto-lookup from Google Contacts)"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_whatsapp_contacts",
            "description": "List all saved WhatsApp contacts.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_gchat_webhook",
            "description": "Save a Google Chat webhook URL with a friendly name so it can be used by voice. Use when user says 'add a Google Chat webhook for X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Friendly name (e.g. 'dev team', 'marketing')"},
                    "url":  {"type": "string", "description": "The full webhook URL"},
                },
                "required": ["name", "url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_gchat_webhooks",
            "description": "List all saved Google Chat webhook shortcuts.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Store a personal fact about the user for future sessions. Use when user says 'remember that X' or 'note that X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember, written as a statement (e.g. 'User drives a Tesla')"},
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_fact",
            "description": "Remove a stored memory. Use when user says 'forget that X' or 'don't remember X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Keyword to match facts to remove"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_facts",
            "description": "List all stored memories. Use when user asks 'what do you remember about me' or 'what do you know about me'.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Fetch the full text content of a URL. Use this after web_search when the snippets are too short or cut off. Especially useful for sports results, schedules, and detailed data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current time in any city or country. ALWAYS use this for time questions — never use web_search for time. Works for any location: 'Montreal', 'Tokyo', 'London', 'local', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City or country name (e.g. 'Montreal', 'Japan', 'local')"},
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hot_reload",
            "description": f"Reload a Python module so recent edits take effect without restarting {_get_name()}. Called automatically after edits, but can also be triggered manually.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the .py file to reload (relative to workspace root)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_block",
            "description": "Remove a multi-line block from a file between two marker strings (inclusive). Use for deleting whole functions, classes, or multi-line dict/list entries. Always read_file first to get exact markers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root"},
                    "start_text": {"type": "string", "description": "Exact text where the block starts"},
                    "end_text": {"type": "string", "description": "Exact text where the block ends"},
                },
                "required": ["path", "start_text", "end_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application or file on the computer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "App name to open"},
                },
                "required": ["name"],
            },
        },
    },
]


_FILLER_ENDINGS = [
    r"[Ss]hall I [^?]{0,80}\?",
    r"[Ww]ould you like [^?]{0,80}\?",
    r"[Ii]s there anything else[^?]{0,60}\?",
    r"[Ll]et me know if[^.]{0,80}\.",
    r"[Ll]et me know (how|what)[^.]{0,80}\.",
    r"[Hh]ow can I (assist|help) you[^?]{0,40}\?",
    r"[Ff]eel free to [^.]{0,60}\.",
]

def _clean_response(text: str) -> str:
    """Strip think blocks, markdown, URLs, and filler phrases for clean TTS output."""
    # Remove think blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Remove markdown links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove bare URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove bold/italic markers **text** -> text, *text* -> text, __text__ -> text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    # Remove markdown headers ### -> nothing
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Convert numbered lists "1. " -> just the text
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    # Convert bullet points "- " or "• " -> nothing
    text = re.sub(r'^[\-•▸◆▶]\s+', '', text, flags=re.MULTILINE)
    # Strip filler ending sentences
    for pattern in _FILLER_ENDINGS:
        text = re.sub(pattern, '', text)
    # Collapse multiple newlines/spaces
    text = re.sub(r'\n{3,}', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def _format_emails(raw_result: str) -> str:
    """
    Parse the raw email tool result and return a clean numbered list.
    This bypasses the LLM for the initial listing to avoid hallucination.
    """
    emails = raw_result.split("\n\n---\n\n")
    lines = [f"Here are your {len(emails)} emails:"]
    for i, block in enumerate(emails, 1):
        sender, subject = "", ""
        for line in block.splitlines():
            if line.startswith("From:"):
                sender = line[5:].strip()
            elif line.startswith("Subject:"):
                subject = line[8:].strip()
        lines.append(f"{i}. {sender} — {subject}")
    return "\n".join(lines)


def _dispatch_tool(name: str, args: dict) -> str:
    try:
        if name == "read_emails":
            from agent.tools.email_tool import read_emails
            return read_emails(**args)
        elif name == "get_calendar_events":
            from agent.tools.calendar_tool import get_calendar_events
            return get_calendar_events(**args)
        elif name == "set_reminder":
            from agent.tools.reminder_tool import set_reminder
            return set_reminder(**args)
        elif name == "list_reminders":
            from agent.tools.reminder_tool import list_reminders
            return list_reminders(**args)
        elif name == "cancel_reminder":
            from agent.tools.reminder_tool import cancel_reminder
            return cancel_reminder(**args)
        elif name == "add_todo":
            from agent.tools.todo_tool import add_todo
            return add_todo(**args)
        elif name == "clear_todos":
            from agent.tools.todo_tool import clear_todos
            return clear_todos(**args)
        elif name == "list_todos":
            from agent.tools.todo_tool import list_todos
            return list_todos(**args)
        elif name == "complete_todo":
            from agent.tools.todo_tool import complete_todo
            return complete_todo(**args)
        elif name == "web_search":
            from agent.tools.search_tool import web_search
            return web_search(**args)
        elif name == "open_app":
            from agent.tools.system_tool import open_app
            return open_app(**args)
        elif name == "read_file":
            from agent.tools.code_tool import read_file
            return read_file(**args)
        elif name == "append_file":
            from agent.tools.code_tool import append_file
            return append_file(**args)
        elif name == "remove_line":
            from agent.tools.code_tool import remove_line
            return remove_line(**args)
        elif name == "remove_block":
            from agent.tools.code_tool import remove_block
            return remove_block(**args)
        elif name == "hot_reload":
            from agent.tools.code_tool import hot_reload
            return hot_reload(**args)
        elif name == "get_time":
            from agent.tools.time_tool import get_time
            return get_time(**args)
        elif name == "fetch_page":
            from agent.tools.search_tool import fetch_page
            return fetch_page(**args)
        elif name == "compose_message":
            from agent.tools.compose_tool import compose_message
            return compose_message(**args)
        elif name == "lookup_phone_number":
            from agent.tools.compose_tool import lookup_phone_number
            return lookup_phone_number(**args)
        elif name == "lookup_contact_email":
            from agent.tools.compose_tool import lookup_contact_email
            return lookup_contact_email(**args)
        elif name == "add_whatsapp_contact":
            from agent.tools.compose_tool import add_whatsapp_contact
            return add_whatsapp_contact(**args)
        elif name == "list_whatsapp_contacts":
            from agent.tools.compose_tool import list_whatsapp_contacts
            return list_whatsapp_contacts(**args)
        elif name == "add_gchat_webhook":
            from agent.tools.compose_tool import add_gchat_webhook
            return add_gchat_webhook(**args)
        elif name == "list_gchat_webhooks":
            from agent.tools.compose_tool import list_gchat_webhooks
            return list_gchat_webhooks(**args)
        elif name == "remember_fact":
            from memory.context import remember_fact
            return remember_fact(**args)
        elif name == "forget_fact":
            from memory.context import forget_fact
            return forget_fact(**args)
        elif name == "list_facts":
            from memory.context import list_facts
            return list_facts(**args)
        elif name == "write_file":
            from agent.tools.code_tool import write_file
            return write_file(**args)
        elif name == "edit_file":
            from agent.tools.code_tool import edit_file
            return edit_file(**args)
        elif name == "list_files":
            from agent.tools.code_tool import list_files
            return list_files(**args)
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error ({name}): {e}"


class Brain:
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.history: list[dict] = []
        print(f"[Brain] Using model: {OLLAMA_MODEL}")

    def _trim_history(self):
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def _detect_file_edit(self, user_input: str):
        """
        Detect if user wants to edit a specific file. Returns resolved path or None.
        Handles spoken filenames like "system tool dot py" -> "agent/tools/system_tool.py".
        """
        edit_verbs = ['edit', 'modify', 'update', 'insert',
                      'append', 'remove', 'delete', 'fix', 'refactor', 'rename', 'clear', 'replace']
        # Skip phrases that are clearly tool/contact operations not file edits
        skip_phrases = ['whatsapp contact', 'gchat webhook', 'whatsapp number',
                        'reminder', 'todo', 'calendar', 'email to', 'message to',
                        'add contact', 'save contact']
        user_lower = user_input.lower()
        if any(p in user_lower for p in skip_phrases):
            return None
        if not any(v in user_lower for v in edit_verbs):
            return None

        # Try exact match first (typed input)
        match = re.search(r'[\w./\\-]+\.[a-zA-Z0-9]{1,10}\b', user_input)
        if match:
            candidate = match.group(0)
            # Verify it exists, if not try fuzzy
            from agent.tools.code_tool import _WORKSPACE
            if (_WORKSPACE / candidate).exists():
                return candidate

        # Fuzzy match: normalize spoken input and walk workspace files
        # "system tool dot py" / "systemtools.py" / "system tools" -> system_tool.py
        spoken = user_input.lower()
        spoken_clean = re.sub(r'\bdot\b', '.', spoken)          # "dot py" -> ".py"
        spoken_clean = re.sub(r'[^a-z0-9.]', '', spoken_clean)    # strip spaces/punctuation

        from agent.tools.code_tool import _WORKSPACE
        best_match = None
        best_score = 0

        # Extract meaningful words from spoken input (ignore common verbs/prepositions)
        stopwords = {'the', 'a', 'an', 'in', 'from', 'to', 'of', 'at', 'on',
                     'edit', 'add', 'remove', 'delete', 'update', 'change', 'fix',
                     'file', 'dot', 'py', 'and', 'or', 'my', 'this', 'that'}
        spoken_words = [w for w in re.split(r'\W+', spoken) if w and w not in stopwords]

        for p in _WORKSPACE.rglob('*'):
            if not p.is_file():
                continue
            if p.suffix not in ('.py', '.json', '.txt', '.env', '.md', '.yaml', '.js', '.ts', '.toml', '.cfg'):
                continue

            stem_clean = re.sub(r'[^a-z0-9]', '', p.stem.lower())   # "systemtool"
            stem_parts = re.split(r'[_\-]', p.stem.lower())          # ["system", "tool"]

            score = 0.0

            # Strong signal: spoken word is a substring of the stem or vice versa
            for word in spoken_words:
                if word in stem_clean:
                    score += len(word) / max(len(stem_clean), 1) * 2.0
                elif stem_clean in word:
                    score += 0.8

            # Strong signal: spoken word exactly matches one of the stem parts
            for word in spoken_words:
                if word in stem_parts:
                    score += 1.5

            # Boost if extension explicitly mentioned
            ext = p.suffix.lstrip('.')
            if ext in spoken or f'dot {ext}' in spoken or f'.{ext}' in spoken_clean:
                score += 0.5

            # Boost if parent directory mentioned
            for part in p.parts[:-1]:
                part_l = part.lower()
                if part_l in spoken_words or part_l in spoken_clean:
                    score += 0.4

            # Penalize longer stems (prefer specific matches)
            score = score / (1 + len(stem_clean) * 0.02)

            if score > best_score and score > 0.8:
                best_score = score
                best_match = str(p.relative_to(_WORKSPACE))

        return best_match


    def think(self, user_input: str, verbose: bool = False) -> str:
        self.history.append({"role": "user", "content": user_input})
        self._trim_history()

        # If user wants to edit a file, pre-read it so LLM has real content
        file_path = self._detect_file_edit(user_input)
        if file_path:
            return self._force_read_then_edit(user_input, file_path, verbose)

        from datetime import datetime
        from memory.context import get_memory_context
        from config import ASSISTANT_NAME
        now_str    = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        memory_ctx = get_memory_context()
        system     = SYSTEM_PROMPT_TEMPLATE.format(
            datetime_now=now_str,
            assistant_name=ASSISTANT_NAME,
        )
        if memory_ctx:
            system = system + f"\n\n{memory_ctx}"
        messages = [{"role": "system", "content": system}] + self.history

        for step in range(8):
            if verbose:
                print(f"[Brain] LLM call (step {step + 1})...")

            response = client.chat(
                model=OLLAMA_MODEL,
                messages=messages,
                tools=TOOLS,
            )

            msg = response.message

            if msg.tool_calls:
                tool_results = []

                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ]
                })

                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = tc.function.arguments if isinstance(tc.function.arguments, dict) else {}
                    if verbose:
                        print(f"[Brain] → {name}({args})")
                    result = _dispatch_tool(name, args)
                    if verbose:
                        print(f"[Brain] ← {result[:120]}")

                    tool_results.append((name, result))
                    messages.append({"role": "tool", "content": result})

                # If the ONLY tool called was read_emails, format it directly
                # and skip the LLM to avoid hallucination
                if len(tool_results) == 1 and tool_results[0][0] == "read_emails":
                    text = _format_emails(tool_results[0][1])
                    # Still add to history so follow-up questions have context
                    self.history.append({"role": "assistant", "content": text})
                    # Also inject full content into history as a system note for follow-ups
                    self.history.append({
                        "role": "system",
                        "content": f"Full email content for follow-up questions:\n{tool_results[0][1]}"
                    })
                    return text

                continue

            text = _clean_response(msg.content or "")
            self.history.append({"role": "assistant", "content": text})
            return text

        return "I ran into an issue processing that. Try again."

    def _force_read_then_edit(self, user_input: str, path: str, verbose: bool) -> str:
        """
        Pre-read a file then let LLM edit it with full visibility of real content.
        Prevents hallucination of file contents.
        """
        from agent.tools.code_tool import read_file
        file_content = read_file(path)
        if verbose:
            print(f"[Brain] Pre-read {path} ({len(file_content)} chars)")

        prompt = (
            f"EXACT current content of {path}:\n\n"
            f"{file_content}\n\n"
            f"Task: {user_input}\n\n"
            "Rules:\n"
            "- To REMOVE a single line or entry: use remove_line with a keyword on that line.\n"
            "- To REMOVE multiple lines or a whole block (function, class, section): use remove_block with start and end markers.\n"
            "- To ADD inside a dict or list: use edit_file, find the last entry as old_text, replace with last entry + new entry.\n"
            "- To MODIFY existing text: use edit_file with exact text from the file as old_text.\n"
            "- NEVER use append_file or write_file for editing existing files."
        )

        from datetime import datetime
        from config import ASSISTANT_NAME
        now_str = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        system = SYSTEM_PROMPT_TEMPLATE.format(
            datetime_now=now_str,
            assistant_name=ASSISTANT_NAME,
        )
        messages = [
            {"role": "system", "content": system},
        ] + self.history[:-1] + [
            {"role": "user", "content": prompt}
        ]

        for step in range(4):
            if verbose:
                print(f"[Brain] Edit LLM call (step {step + 1})...")
            response = client.chat(model=OLLAMA_MODEL, messages=messages, tools=TOOLS)
            msg = response.message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ]
                })
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = tc.function.arguments if isinstance(tc.function.arguments, dict) else {}
                    if verbose:
                        print(f"[Brain] → {name}({args})")
                    result = _dispatch_tool(name, args)
                    if verbose:
                        print(f"[Brain] ← {result[:120]}")
                    messages.append({"role": "tool", "content": result})
                continue

            text = _clean_response(msg.content or "")
            self.history.append({"role": "assistant", "content": text})
            return text

        return "Could not complete the file edit."


    def reset(self):
        self.history = []