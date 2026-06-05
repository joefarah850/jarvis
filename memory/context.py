"""
Jarvis long-term memory.

Two types of memory:
- Explicit: things you tell Jarvis to remember ("remember that I drive a Tesla")
- Extracted: facts the LLM pulls from the conversation at session end, validated by you

Stored as plain JSON — human-readable and editable.
"""
import json
import re
from pathlib import Path
from datetime import datetime

import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OLLAMA_MODEL, OLLAMA_BASE_URL
from ollama import Client

client     = Client(host=OLLAMA_BASE_URL)
MEMORY_FILE = Path(__file__).parent.parent / "memory.json"

def _get_name() -> str:
    """Get the assistant name from config."""
    try:
        from config import ASSISTANT_NAME
        return ASSISTANT_NAME
    except Exception:
        return "Jarvis"

# ── Storage ───────────────────────────────────────────────────────────────────

def load_memory() -> dict:
    if not MEMORY_FILE.exists():
        return {"facts": [], "updated": None}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_memory(memory: dict):
    memory["updated"] = datetime.now().isoformat()
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


def get_memory_context() -> str:
    """
    Returns a formatted string of known facts to inject into the system prompt.
    Empty string if no facts stored yet.
    """
    memory = load_memory()
    facts  = memory.get("facts", [])
    if not facts:
        return ""
    lines = ["What I know about you:"]
    for f in facts:
        lines.append(f"- {f['fact']}")
    return "\n".join(lines)


def remember_fact(fact: str) -> str:
    """
    Explicitly store a fact. Called when user says 'remember that X'.
    No LLM validation needed — stored verbatim.
    """
    memory = load_memory()
    # Avoid duplicates
    existing = [f["fact"].lower() for f in memory["facts"]]
    if fact.lower() in existing:
        return f"Already noted: {fact}"
    memory["facts"].append({
        "fact":   fact,
        "source": "explicit",
        "added":  datetime.now().isoformat(),
    })
    save_memory(memory)
    return f"Noted: {fact}"


def forget_fact(keyword: str) -> str:
    """Remove facts containing a keyword."""
    memory  = load_memory()
    before  = len(memory["facts"])
    memory["facts"] = [f for f in memory["facts"] if keyword.lower() not in f["fact"].lower()]
    removed = before - len(memory["facts"])
    if removed == 0:
        return f"No facts found containing '{keyword}'."
    save_memory(memory)
    return f"Removed {removed} fact(s) containing '{keyword}'."


def list_facts() -> str:
    memory = load_memory()
    facts  = memory.get("facts", [])
    if not facts:
        return "No memories stored yet."
    lines = [f"{i+1}. {f['fact']}" for i, f in enumerate(facts)]
    return "Stored memories:\n" + "\n".join(lines)


# ── Session extraction ────────────────────────────────────────────────────────

def extract_facts_from_conversation(history: list[dict]) -> list[str]:
    """
    Ask the LLM to extract memorable facts from the conversation.
    Returns a list of candidate fact strings.
    """
    if not history:
        return []

    # Build a clean transcript
    lines = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"User: {content}")
        elif role == "assistant":
            lines.append(f"{_get_name()}: {content}")

    transcript = "\n".join(lines[-40:])  # last 20 turns max

    prompt = (
        "Read this conversation and extract factual personal information about the user "
        "that would be useful to remember for future conversations.\n\n"
        "Rules:\n"
        "- Only extract concrete facts (preferences, possessions, habits, recurring events, names)\n"
        "- Do NOT extract things already answered by tools (search results, emails read, etc.)\n"
        "- Do NOT extract questions or hypotheticals\n"
        "- Write each fact as a short statement starting with 'User' (e.g. 'User drives a Tesla')\n"
        "- If there are no memorable personal facts, return an empty list\n"
        "- Return ONLY a JSON array of strings, nothing else\n\n"
        f"Conversation:\n{transcript}\n\n"
        "JSON array of facts:"
    )

    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.message.content or "[]"
        # Strip think blocks
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # Extract JSON array
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if not match:
            return []
        facts = json.loads(match.group(0))
        return [f for f in facts if isinstance(f, str) and f.strip()]
    except Exception:
        return []


# ── End-of-session review ─────────────────────────────────────────────────────

class MemoryReview:
    """
    Interactive end-of-session memory review.
    Extracts candidate facts, lets user validate/edit/skip each one.
    """

    def __init__(self, speaker=None):
        self.speaker    = speaker
        self.candidates: list[str] = []

    def _say(self, text: str):
        print(f"[{_get_name()}] {text}")
        if self.speaker:
            self.speaker.speak(text)

    def run(self, history: list[dict], listen_fn=None, transcribe_fn=None) -> int:
        """
        Run the review flow. Returns number of facts saved.
        listen_fn and transcribe_fn are optional — if not provided, uses text input.
        """
        self._say("Reviewing our conversation for anything worth remembering...")

        candidates = extract_facts_from_conversation(history)

        if not candidates:
            self._say("Nothing new to remember from this session.")
            return 0

        self._say(f"I picked up {len(candidates)} thing{'s' if len(candidates) > 1 else ''}:")
        for i, fact in enumerate(candidates, 1):
            self._say(f"{i}. {fact}")

        self._say("Should I save these? Say 'yes', 'no', 'edit', or name a number to skip.")

        saved = 0
        pending = list(enumerate(candidates, 1))

        while pending:
            if listen_fn and transcribe_fn:
                audio = listen_fn(verbose=False)
                response = transcribe_fn(audio) if audio is not None else ""
            else:
                response = input("You: ").strip()

            response_l = response.lower()

            if any(w in response_l for w in ["yes", "save", "all", "yep", "sure"]):
                for _, fact in pending:
                    remember_fact(fact)
                    saved += 1
                self._say(f"Saved {saved} memory{'s' if saved > 1 else ''}.")
                break

            elif any(w in response_l for w in ["no", "skip", "none", "nope", "forget"]):
                self._say("Nothing saved.")
                break

            elif "edit" in response_l:
                # Let user specify which one and what to change
                self._say("Which one and what should it say?")
                if listen_fn and transcribe_fn:
                    audio = listen_fn(verbose=False)
                    edit_response = transcribe_fn(audio) if audio is not None else ""
                else:
                    edit_response = input("You: ").strip()

                # Use LLM to parse the edit instruction
                updated = _apply_edit(pending, edit_response)
                if updated:
                    pending = updated
                    self._say("Updated. Here are the revised facts:")
                    for i, fact in pending:
                        self._say(f"{i}. {fact}")
                    self._say("Save these?")
                else:
                    self._say("Couldn't parse that edit. Try again.")

            else:
                # Treat as confirmation and loop
                self._say("Say 'yes' to save all, 'no' to skip, or 'edit' to change something.")

        return saved


def _apply_edit(pending: list[tuple], edit_instruction: str) -> list[tuple] | None:
    """
    Use the LLM to apply an edit instruction to the pending facts list.
    e.g. "Edit number 1, I drive a Tesla not a BMW" -> updates fact 1
    """
    facts_str = "\n".join(f"{i}. {fact}" for i, fact in pending)
    prompt = (
        f"Current facts:\n{facts_str}\n\n"
        f"Edit instruction: {edit_instruction}\n\n"
        "Apply the edit and return the updated list as a JSON array of strings "
        "in the same order. Return ONLY the JSON array."
    )
    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.message.content or "[]"
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if not match:
            return None
        updated_facts = json.loads(match.group(0))
        # Re-pair with original indices
        return list(zip([i for i, _ in pending], updated_facts))
    except Exception:
        return None