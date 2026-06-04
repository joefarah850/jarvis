"""
Run this to validate the full audio pipeline before touching the agent.
Say something → it transcribes → Jarvis repeats it back.
Ctrl+C to exit.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from audio.listener import listen_once
from audio.transcriber import Transcriber
from audio.speaker import Speaker


def main():
    transcriber = Transcriber()
    speaker = Speaker()

    speaker.speak("Audio pipeline online. Say something.")

    while True:
        print("\n[Test] Listening...")
        audio = listen_once(verbose=True)

        if audio is None:
            print("[Test] No speech detected, trying again.")
            continue

        print("[Test] Transcribing...")
        text = transcriber.transcribe(audio)

        if not text:
            print("[Test] Empty transcription, skipping.")
            continue

        print(f"[Test] You said: {text}")
        speaker.speak(f"You said: {text}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Test] Stopped.")