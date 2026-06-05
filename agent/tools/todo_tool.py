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


def complete_todo(task_id: int = 0, task_name: str = "") -> str:
    """Mark a task as done by ID or by name (fuzzy match)."""
    todos = _load()

    # Match by ID first
    if task_id:
        for t in todos:
            if t["id"] == task_id:
                t["done"] = True
                _save(todos)
                return f"Marked as done: '{t['task']}'"
        return f"Task #{task_id} not found."

    # Match by name
    if task_name:
        name_l = task_name.lower()
        best, best_score = None, 0
        for t in todos:
            task_l = t["task"].lower()
            # Score by overlap
            score = sum(1 for w in name_l.split() if w in task_l)
            if score > best_score:
                best_score = score
                best = t
        if best and best_score > 0:
            best["done"] = True
            _save(todos)
            return f"Marked as done: '{best['task']}'"
        return f"Could not find a task matching '{task_name}'."

    return "Please provide a task ID or name."


def clear_todos(completed_only: bool = False) -> str:
    """Clear all todos or just completed ones."""
    todos = _load()
    if not todos:
        return "Todo list is already empty."
    if completed_only:
        before = len(todos)
        todos  = [t for t in todos if not t["done"]]
        removed = before - len(todos)
        _save(todos)
        return f"Removed {removed} completed task(s)."
    _save([])
    return f"Cleared all {len(todos)} tasks from the todo list."