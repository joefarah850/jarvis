import sounddevice as sd
import numpy as np
import platform
from pathlib import Path
from kokoro_onnx import Kokoro
import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import KOKORO_VOICE

_REPO_ROOT = Path(__file__).parent.parent

# Pick the right model file based on platform
# Windows + NVIDIA GPU → fp16-gpu, everything else → fp16 (CPU/MPS)
def _find_model() -> Path:
    candidates = [
        _REPO_ROOT / "kokoro-v1.0.fp16-gpu.onnx",  # Windows CUDA
        _REPO_ROOT / "kokoro-v1.0.fp16.onnx",       # Mac / Linux CPU
        _REPO_ROOT / "kokoro-v1.0.onnx",            # Full fp32 fallback
        _REPO_ROOT / "kokoro-v1.0.int8.onnx",       # Smallest fallback
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"No Kokoro model file found in {_REPO_ROOT}.\n"
        "Download from: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0\n"
        "Windows+GPU: kokoro-v1.0.fp16-gpu.onnx\n"
        "Mac/Linux:   kokoro-v1.0.fp16.onnx"
    )

VOICES_PATH = _REPO_ROOT / "voices-v1.0.bin"


class Speaker:
    def __init__(self, voice: str = None):
        voice = voice or KOKORO_VOICE or "am_michael"
        model_path = _find_model()
        print(f"[Speaker] Loading Kokoro TTS ({model_path.name}, voice: {voice})...")
        if not VOICES_PATH.exists():
            raise FileNotFoundError(
                f"voices-v1.0.bin not found in {_REPO_ROOT}.\n"
                "Download from: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0"
            )
        self.kokoro = Kokoro(str(model_path), str(VOICES_PATH))
        self.voice  = voice
        print("[Speaker] Ready")

    def speak(self, text: str, speed: float = 1.0):
        if not text.strip():
            return
        samples, sample_rate = self.kokoro.create(
            text, voice=self.voice, speed=speed, lang="en-us",
        )
        sd.play(samples, samplerate=sample_rate)
        sd.wait()

    def speak_nonblocking(self, text: str, speed: float = 1.0):
        import threading
        t = threading.Thread(target=self.speak, args=(text, speed), daemon=True)
        t.start()