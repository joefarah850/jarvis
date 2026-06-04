"""
Test the LLM brain in text mode — no audio needed.
Type messages, Jarvis responds. Type 'quit' to exit.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.brain import Brain

def main():
    brain = Brain()
    print("\n[Test] Brain ready. Type something (or 'quit' to exit).\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            break

        response = brain.think(user_input, verbose=True)
        print(f"\nJarvis: {response}\n")

if __name__ == "__main__":
    main()