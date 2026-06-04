"""
Open applications and files — cross-platform (Windows, Mac, Linux).
"""
import subprocess
import platform
import os

IS_WINDOWS = platform.system() == "Windows"
IS_MAC     = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"

# App name → command mapping per platform
APP_MAP_WINDOWS = {
    "chrome":        "chrome",
    "google chrome": "chrome",
    "firefox":       "firefox",
    "edge":          "msedge",
    "notepad":       "notepad",
    "calculator":    "calc",
    "explorer":      "explorer",
    "file explorer": "explorer",
    "spotify":       "spotify",
    "discord":       "discord",
    "vscode":        "code",
    "vs code":       "code",
    "terminal":      "wt",
    "powershell":    "powershell",
    "word":          "winword",
    "excel":         "excel",
    "outlook":       "outlook",
    "paint":         "mspaint",
    "task manager":  "taskmgr",
}

APP_MAP_MAC = {
    "chrome":        "Google Chrome",
    "google chrome": "Google Chrome",
    "firefox":       "Firefox",
    "safari":        "Safari",
    "finder":        "Finder",
    "terminal":      "Terminal",
    "iterm":         "iTerm",
    "vscode":        "Visual Studio Code",
    "vs code":       "Visual Studio Code",
    "spotify":       "Spotify",
    "discord":       "Discord",
    "slack":         "Slack",
    "zoom":          "Zoom",
    "notes":         "Notes",
    "calendar":      "Calendar",
    "mail":          "Mail",
    "messages":      "Messages",
    "calculator":    "Calculator",
    "activity monitor": "Activity Monitor",
}

APP_MAP_LINUX = {
    "chrome":        "google-chrome",
    "google chrome": "google-chrome",
    "firefox":       "firefox",
    "terminal":      "gnome-terminal",
    "vscode":        "code",
    "vs code":       "code",
    "spotify":       "spotify",
    "discord":       "discord",
    "slack":         "slack",
    "calculator":    "gnome-calculator",
    "files":         "nautilus",
    "file manager":  "nautilus",
}


def open_app(name: str) -> str:
    key = name.lower().strip()

    try:
        if IS_WINDOWS:
            cmd = APP_MAP_WINDOWS.get(key, key)
            subprocess.Popen(
                f'start "" "{cmd}"',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        elif IS_MAC:
            app = APP_MAP_MAC.get(key, name)
            subprocess.Popen(
                ["open", "-a", app],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        else:  # Linux
            cmd = APP_MAP_LINUX.get(key, key)
            subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        return f"Opened {name}."

    except Exception as e:
        return f"Couldn't open '{name}': {e}"


def open_file(path: str) -> str:
    """Open a file with its default application."""
    if not os.path.exists(path):
        return f"File not found: {path}"
    try:
        if IS_WINDOWS:
            os.startfile(path)
        elif IS_MAC:
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return f"Opened: {path}"
    except Exception as e:
        return f"Couldn't open file: {e}"