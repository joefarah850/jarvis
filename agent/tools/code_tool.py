"""
File editing tools — lets Jarvis read and modify files on the local machine.
Workspace root is configurable via WORKSPACE_ROOT in .env.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import WORKSPACE_ROOT

_REPO_ROOT = Path(__file__).parent.parent.parent
_WORKSPACE = Path(WORKSPACE_ROOT).resolve() if WORKSPACE_ROOT else _REPO_ROOT.resolve()


def _resolve(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = _WORKSPACE / p
    p = p.resolve()
    if not str(p).startswith(str(_WORKSPACE)):
        raise PermissionError(
            f"Access denied: '{path}' is outside the workspace ({_WORKSPACE}).\n"
            f"Set WORKSPACE_ROOT in .env to allow access to other directories."
        )
    return p


def read_file(path: str) -> str:
    """Read and return the full contents of a file."""
    try:
        p = _resolve(path)
        if not p.exists():
            return f"File not found: {path}"
        if p.stat().st_size > 200_000:
            return f"File too large (>{200_000} bytes): {path}"
        return p.read_text(encoding="utf-8", errors="ignore")
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error reading {path}: {e}"


def append_file(path: str, content: str) -> str:
    """
    Add lines to the END of an existing file without touching the rest.
    Use this when the user wants to ADD something to a file (new variables, new functions, etc.).
    Always prefer this over write_file for existing files.
    """
    try:
        p = _resolve(path)
        if not p.exists():
            return f"File not found: {path}. Use write_file to create a new file."
        existing = p.read_text(encoding="utf-8", errors="ignore")
        # Ensure we start on a new line
        separator = "\n" if existing and not existing.endswith("\n") else ""
        p.write_text(existing + separator + content + "\n", encoding="utf-8")
        result = f"Appended to {path}:\n{content}"
        if p.suffix == ".py":
            reload_result = hot_reload(path)
            result += f"\n{reload_result}"
        return result
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error appending to {path}: {e}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """
    Replace a specific piece of text in a file with new text.
    Use this to MODIFY existing lines.
    Always call read_file first to get the exact text to replace.
    NEVER use this to add new content — use append_file instead.
    """
    try:
        p = _resolve(path)
        if not p.exists():
            return f"File not found: {path}"

        content = p.read_text(encoding="utf-8", errors="ignore")

        if old_text not in content:
            # Find nearby lines to help the LLM correct itself
            needle = old_text.strip().lower()[:20]
            hints = [l for l in content.splitlines() if needle in l.lower()]
            hint_str = "\n".join(hints[:3]) if hints else "(no similar lines found)"
            return (
                f"Text not found in {path}.\n"
                f"Looked for: {repr(old_text[:120])}\n"
                f"Similar lines in the file (use exact text from these):\n{hint_str}\n"
                "Pay attention to quote style (single vs double) and whitespace."
            )

        updated = content.replace(old_text, new_text, 1)
        p.write_text(updated, encoding="utf-8")
        result = f"Done. In {path}, replaced:\n- {repr(old_text[:80])}\n+ {repr(new_text[:80])}"
        # Auto hot-reload if it's a Python file
        if p.suffix == ".py":
            reload_result = hot_reload(path)
            result += f"\n{reload_result}"
        return result

    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error editing {path}: {e}"


def write_file(path: str, content: str) -> str:
    """
    Create a NEW file with the given content.
    WARNING: Completely overwrites the file if it already exists.
    Only use this for brand new files. For existing files use append_file or edit_file.
    """
    try:
        p = _resolve(path)
        if p.exists():
            return (
                f"WARNING: {path} already exists. write_file would overwrite it entirely.\n"
                "Use append_file to add content, or edit_file to modify specific lines.\n"
                "If you truly want to overwrite, call write_file with overwrite=true."
            )
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Created: {path} ({len(content)} chars)"
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error writing {path}: {e}"


def list_files(directory: str = ".") -> str:
    """List files and folders in a directory."""
    try:
        p = _resolve(directory)
        if not p.exists():
            return f"Directory not found: {directory}"
        if not p.is_dir():
            return f"Not a directory: {directory}"

        lines = []
        for item in sorted(p.iterdir()):
            if item.name.startswith('.'):
                continue
            if item.is_dir():
                lines.append(f"[dir]  {item.name}/")
            else:
                size = item.stat().st_size
                size_str = f"{size:,} B" if size < 1024 else f"{size//1024:,} KB"
                lines.append(f"[file] {item.name} ({size_str})")

        return f"Contents of {directory}:\n" + "\n".join(lines) if lines else f"{directory} is empty."

    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error listing {directory}: {e}"


def remove_line(path: str, containing: str) -> str:
    """
    Remove all lines from a file that contain the given substring.
    Much safer than edit_file for deletions — no risk of corrupting surrounding code.
    Use this whenever the user wants to DELETE a line or entry from a file.
    """
    try:
        p = _resolve(path)
        if not p.exists():
            return f"File not found: {path}"

        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
        original_count = len(lines)
        kept = [l for l in lines if containing not in l]
        removed = original_count - len(kept)

        if removed == 0:
            # Show lines that are close so the LLM can correct
            hints = [l.rstrip() for l in lines if containing.split('"')[0].strip().lower() 
                     in l.lower()][:3]
            hint_str = "\n".join(hints) if hints else "(none found)"
            return (
                f"No lines containing {repr(containing)} found in {path}.\n"
                f"Similar lines:\n{hint_str}"
            )

        p.write_text("".join(kept), encoding="utf-8")
        result = f"Removed {removed} line(s) containing {repr(containing)} from {path}."
        if p.suffix == ".py":
            reload_result = hot_reload(path)
            result += f"\n{reload_result}"
        return result

    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error removing line from {path}: {e}"

def _get_name() -> str:
    """Get the assistant name from config."""
    try:
        from config import ASSISTANT_NAME
        return ASSISTANT_NAME
    except Exception:
        return "Jarvis"
    
def hot_reload(path: str) -> str:
    """
    Reload a Python module after editing it so changes take effect
    without restarting Jarvis. Works for tools, brain, config.
    """
    import importlib
    import sys

    try:
        p = _resolve(path)
        if not p.exists():
            return f"File not found: {path}"
        if p.suffix != ".py":
            return f"Hot reload only works for .py files. {path} will take effect on next restart."

        # Convert file path to module name
        # e.g. agent/tools/email_tool.py -> agent.tools.email_tool
        rel = p.relative_to(_WORKSPACE)
        module_name = str(rel.with_suffix("")).replace("\\", ".").replace("/", ".")

        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
            return f"Reloaded {module_name} — changes are live."
        else:
            # Module not loaded yet — import it
            import importlib as il
            il.import_module(module_name)
            return f"Loaded {module_name} — changes are live."

    except Exception as e:
        assistant_name = _get_name()
        return f"Hot reload failed for {path}: {e}\nChanges will apply on next {assistant_name} restart."


def remove_block(path: str, start_text: str, end_text: str) -> str:
    """
    Remove a block of lines from start_text to end_text (inclusive).
    Use for deleting multi-line constructs like functions, classes, or dict blocks.
    Always read_file first to confirm exact start and end markers.
    """
    try:
        p = _resolve(path)
        if not p.exists():
            return f"File not found: {path}"

        content = p.read_text(encoding="utf-8", errors="ignore")

        start_idx = content.find(start_text)
        if start_idx == -1:
            return (
                f"Start marker not found in {path}.\n"
                f"Looked for: {repr(start_text[:80])}\n"
                "Use read_file to get exact text."
            )

        end_idx = content.find(end_text, start_idx)
        if end_idx == -1:
            return (
                f"End marker not found in {path} after start.\n"
                f"Looked for: {repr(end_text[:80])}\n"
                "Use read_file to get exact text."
            )

        # Include the full end line
        end_idx = content.find("\n", end_idx)
        if end_idx == -1:
            end_idx = len(content)
        else:
            end_idx += 1  # include the newline

        removed = content[start_idx:end_idx]
        updated = content[:start_idx] + content[end_idx:]
        p.write_text(updated, encoding="utf-8")

        line_count = removed.count("\n")
        return f"Removed {line_count} lines from {path} (from {repr(start_text[:40])} to {repr(end_text[:40])})."

    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error removing block from {path}: {e}"