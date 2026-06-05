"""
Jarvis — main voice loop.
Wake word → listen → transcribe → think → speak → repeat.
End of session → memory review.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from audio.listener import listen_once
from audio.transcriber import Transcriber
from audio.speaker import Speaker
from agent.brain import Brain
from memory.context import MemoryReview

try:
    from config import WAKE_WORD
except ImportError:
    WAKE_WORD = ""

USE_WAKE_WORD = bool(WAKE_WORD)
EXIT_PHRASES  = {"goodbye", "bye jarvis", "shut down", "exit", "stop", "quit"}


def contains_wake_word(text: str) -> bool:
    return WAKE_WORD.lower() in text.lower()


def is_exit(text: str) -> bool:
    t = text.lower().strip().rstrip(".")
    return any(phrase in t for phrase in EXIT_PHRASES)


def main():
    print("\n" + "=" * 50)
    print("  J.A.R.V.I.S  —  Starting up")
    print("=" * 50 + "\n")

    transcriber = Transcriber()
    speaker     = Speaker()
    brain       = Brain()

    speaker.speak("Systems online. How can I help?")

    # Start UI WebSocket bridge
    from ui.bridge import start_bridge, set_status, add_transcript, push_todos, push_reminders
    start_bridge()

    # Wire compose tool to audio I/O so approval loop can speak/listen
    from agent.tools.compose_tool import set_io
    set_io(speaker, listen_once, transcriber.transcribe)

    # Start reminder background checker and wire audio I/O
    from agent.tools.reminder_tool import start_reminder_checker, set_reminder_io
    set_reminder_io(speaker, listen_once, transcriber.transcribe, brain)
    start_reminder_checker()
    print("[Jarvis] Ready. Ctrl+C to exit.\n")

    while True:
        try:
            # ── Wake word gate ────────────────────────────────────────────
            if USE_WAKE_WORD:
                print(f"[Jarvis] Waiting for '{WAKE_WORD}'...")
                audio = listen_once(verbose=False)
                if audio is None:
                    continue
                trigger = transcriber.transcribe(audio)
                if not trigger or not contains_wake_word(trigger):
                    continue
                print(f"[Jarvis] Activated: '{trigger}'")
                speaker.speak_nonblocking("Yes?")
                set_status("idle")
                time.sleep(0.5)

            # ── Listen ────────────────────────────────────────────
            print("[Jarvis] Listening...")
            set_status("listening")
            audio = listen_once(verbose=False)
            if audio is None:
                set_status("idle")
                continue

            # ── Transcribe ─────────────────────────────────────────
            set_status("thinking")
            text = transcriber.transcribe(audio)
            if not text:
                set_status("idle")
                continue

            print(f"\n[You]    {text}")
            add_transcript("user", text)

            # ── Exit check ──────────────────────────────────────────
            if is_exit(text):
                speaker.speak("One moment.")
                _run_memory_review(brain, speaker, transcriber)
                speaker.speak("Goodbye.")
                print("[Jarvis] Shutting down.")
                break

            # ── Think ───────────────────────────────────────────────
            response = brain.think(text, verbose=True)
            if not response:
                set_status("idle")
                continue

            print(f"[Jarvis] {response}\n")
            add_transcript("jarvis", response)
            push_todos()
            push_reminders()
            set_status("speaking")
            speaker.speak(response)
            set_status("idle")

        except KeyboardInterrupt:
            print("\n[Jarvis] Interrupted.")
            speaker.speak("One moment.")
            _run_memory_review(brain, speaker, transcriber)
            speaker.speak("Goodbye.")
            break
        except Exception as e:
            print(f"[Jarvis] Error: {e}")
            speaker.speak("Something went wrong. Try again.")
            continue


def _run_memory_review(brain: Brain, speaker, transcriber):
    """Run end-of-session memory review if there's conversation history."""
    if len(brain.history) < 2:
        return
    try:
        review = MemoryReview(speaker=speaker)
        review.run(
            history      = brain.history,
            listen_fn    = listen_once,
            transcribe_fn= transcriber.transcribe,
        )
    except Exception as e:
        print(f"[Memory] Review error: {e}")


if __name__ == "__main__":
    main()