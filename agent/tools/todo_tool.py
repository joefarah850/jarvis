"""
Simple local to-do list stored as a JSON file in the repo root.
No external API needed.
"""
import json
import os
from datetime import datetime
from pathlib import Path

TODO_FILE = Path(__file__).parent.parent.parent / "todos.json"


def _load() -> list[dict]:
    if not TODO_FILE.exists():
        return []
    with open(TODO_FILE, "r") as f:
        return json.load(f)


def _save(todos: list[dict]):
    with open(TODO_FILE, "w") as f:
        json.dump(todos, f, indent=2)


def add_todo(task: str, priority: str = "medium") -> str:
    todos = _load()
    item = {
        "id": len(todos) + 1,
        "task": task,
        "priority": priority,
        "done": False,
        "created": datetime.now().isoformat(),
    }
    todos.append(item)
    _save(todos)
    return f"Added: '{task}' (priority: {priority})"


def list_todos(show_done: bool = False) -> str:
    todos = _load()
    if not todos:
        return "No tasks."
    filtered = [t for t in todos if show_done or not t["done"]]
    if not filtered:
        return "No pending tasks."
    lines = []
    for t in filtered:
        status = "✓" if t["done"] else "○"
        lines.append(f"[{status}] #{t['id']} ({t['priority']}) {t['task']}")
    return "\n".join(lines)


def complete_todo(task_id: int) -> str:
    todos = _load()
    for t in todos:
        if t["id"] == task_id:
            t["done"] = True
            _save(todos)
            return f"Marked #{task_id} as done: '{t['task']}'"
    return f"Task #{task_id} not found."