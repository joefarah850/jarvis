#!/bin/bash
# Run Jarvis on Linux

cd "$(dirname "$0")"

if [ ! -f ".venv/bin/python" ]; then
    zenity --error --text="Jarvis not set up. Run: python3 setup.py" 2>/dev/null || \
    echo "ERROR: Run python3 setup.py first"
    exit 1
fi

# Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null; then
    ollama serve &>/dev/null &
    sleep 2
fi

.venv/bin/python main.py &
JARVIS_PID=$!
sleep 3

cd ui
npm start

kill $JARVIS_PID 2>/dev/null