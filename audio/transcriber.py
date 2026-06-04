import numpy as np
import os
import platform
from faster_whisper import WhisperModel

MODEL_SIZE = "large-v3-turbo"


def _patch_cuda_path():
    """Add nvidia pip-package DLL dirs to PATH — Windows only."""
    if platform.system() != "Windows":
        return
    venv = os.environ.get("VIRTUAL_ENV", "")
    nvidia_bin = os.path.join(venv, "Lib", "site-packages", "nvidia")
    if not os.path.isdir(nvidia_bin):
        return
    for pkg in os.listdir(nvidia_bin):
        bin_dir = os.path.join(nvidia_bin, pkg, "bin")
        if os.path.isdir(bin_dir) and bin_dir not in os.environ["PATH"]:
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]


def _best_device():
    """Pick the best available compute device."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import WHISPER_DEVICE, WHISPER_COMPUTE_TYPE

    # Honour explicit config
    if WHISPER_DEVICE and WHISPER_COMPUTE_TYPE:
        return WHISPER_DEVICE, WHISPER_COMPUTE_TYPE

    system = platform.system()

    if system == "Windows":
        # Try CUDA first
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda", "float16"
        except ImportError:
            pass
        return "cpu", "int8"

    elif system == "Darwin":
        # Apple Silicon — MPS not supported by ctranslate2, use int8 CPU
        # which is still fast thanks to Apple's AMX instructions
        return "cpu", "int8"

    else:
        # Linux — try CUDA
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda", "float16"
        except ImportError:
            pass
        return "cpu", "int8"


class Transcriber:
    def __init__(self, language: str = "en"):
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from config import WHISPER_LANGUAGE
        self.language = WHISPER_LANGUAGE or language

        _patch_cuda_path()
        device, compute_type = _best_device()
        print(f"[Transcriber] Loading Whisper {MODEL_SIZE} on {device} ({compute_type})...")
        self.model = WhisperModel(MODEL_SIZE, device=device, compute_type=compute_type)
        print("[Transcriber] Ready")

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        return " ".join(seg.text.strip() for seg in segments).strip()