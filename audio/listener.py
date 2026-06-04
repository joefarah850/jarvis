import numpy as np
import sounddevice as sd
import torch
import time
import threading
import platform
from collections import deque
from silero_vad import load_silero_vad
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import AUDIO_DEVICE_NAME, VAD_THRESHOLD, VAD_SILENCE_TIMEOUT

model = load_silero_vad()

TARGET_SR           = 16000
VAD_SAMPLES         = 512
PRE_ROLL_CHUNKS     = 10
MIN_SPEECH_DURATION = 0.4

IS_WINDOWS = platform.system() == "Windows"
IS_MAC     = platform.system() == "Darwin"

LOOPBACK_KEYWORDS = ['stereo mix', 'what u hear', 'wave out', 'loopback', 'output']
MIC_KEYWORDS      = ['mic', 'microphone', 'input']

# Preferred host APIs by platform
PREFERRED_APIS_WINDOWS = ['Windows WDM-KS', 'Windows WASAPI', 'MME']
PREFERRED_APIS_MAC     = ['Core Audio']
PREFERRED_APIS_LINUX   = ['ALSA', 'PulseAudio', 'JACK Audio Connection Kit']


def _is_loopback(name: str) -> bool:
    return any(k in name.lower() for k in LOOPBACK_KEYWORDS)

def _is_mic(name: str) -> bool:
    return any(k in name.lower() for k in MIC_KEYWORDS)


def _find_input_device():
    devices  = sd.query_devices()
    hostapis = sd.query_hostapis()

    def api_name(idx):
        return hostapis[idx]['name'] if idx < len(hostapis) else ''

    input_devices = [
        (i, d, api_name(d['hostapi']))
        for i, d in enumerate(devices)
        if d['max_input_channels'] > 0 and not _is_loopback(d['name'])
    ]

    # User-specified device
    if AUDIO_DEVICE_NAME:
        for i, d, api in input_devices:
            if AUDIO_DEVICE_NAME.lower() in d['name'].lower():
                sr = int(d['default_samplerate'])
                print(f"[Listener] Using configured: [{i}] {d['name']} ({api}) @ {sr}Hz")
                return i, sr

    # Platform-specific preferred APIs
    if IS_WINDOWS:
        preferred_apis = PREFERRED_APIS_WINDOWS
    elif IS_MAC:
        preferred_apis = PREFERRED_APIS_MAC
    else:
        preferred_apis = PREFERRED_APIS_LINUX

    for preferred_api in preferred_apis:
        candidates = [(i, d, api) for i, d, api in input_devices if preferred_api in api]
        candidates.sort(key=lambda x: (0 if _is_mic(x[1]['name']) else 1))
        for i, d, api in candidates:
            sr = int(d['default_samplerate'])
            print(f"[Listener] Auto-detected: [{i}] {d['name']} ({api}) @ {sr}Hz")
            return i, sr

    # Fallback: any working input device
    for i, d, api in input_devices:
        sr = int(d['default_samplerate'])
        print(f"[Listener] Fallback: [{i}] {d['name']} ({api}) @ {sr}Hz")
        return i, sr

    raise RuntimeError(
        "No working microphone found.\n"
        "Set AUDIO_DEVICE_NAME in .env to a partial name from:\n"
        + "\n".join(f"  [{i}] {d['name']}" for i, d, _ in input_devices)
    )


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return audio
    target_len = int(len(audio) * target_sr / orig_sr)
    return np.interp(
        np.linspace(0, len(audio) - 1, target_len),
        np.arange(len(audio)),
        audio,
    ).astype(np.float32)


_cached_device = None


def listen_once(
    silence_timeout: float = VAD_SILENCE_TIMEOUT,
    threshold: float       = VAD_THRESHOLD,
    verbose: bool          = False,
) -> np.ndarray | None:

    global _cached_device
    if _cached_device is None:
        _cached_device = _find_input_device()
    device_index, native_sr = _cached_device
    native_chunk = int(native_sr * 30 / 1000)

    if verbose:
        print("[Listener] Waiting for speech...")

    model.reset_states()
    pre_roll      = deque(maxlen=PRE_ROLL_CHUNKS)
    audio_buffer  = []
    speaking      = False
    silence_start = None
    done_event    = threading.Event()

    def callback(indata, frames, time_info, status):
        nonlocal speaking, silence_start
        chunk = indata[:, 0].copy()

        chunk_16k = _resample(chunk, native_sr, TARGET_SR)
        if len(chunk_16k) < VAD_SAMPLES:
            chunk_16k = np.pad(chunk_16k, (0, VAD_SAMPLES - len(chunk_16k)))
        else:
            chunk_16k = chunk_16k[:VAD_SAMPLES]

        try:
            confidence = model(torch.from_numpy(chunk_16k), TARGET_SR).item()
        except Exception:
            return

        if confidence >= threshold:
            if not speaking:
                speaking      = True
                silence_start = None
                if verbose:
                    print("[Listener] Speech detected")
                audio_buffer.extend(pre_roll)
            audio_buffer.append(chunk)
        elif speaking:
            audio_buffer.append(chunk)
            if silence_start is None:
                silence_start = time.time()
            elif time.time() - silence_start > silence_timeout:
                if verbose:
                    print("[Listener] Silence detected, stopping")
                done_event.set()
        else:
            pre_roll.append(chunk)

    # Try channels 2 then 1 (WDM-KS on Windows needs 2, Mac is fine with 1)
    for channels in ([2, 1] if IS_WINDOWS else [1, 2]):
        try:
            with sd.InputStream(device=device_index, samplerate=native_sr,
                                channels=channels, dtype="float32",
                                blocksize=native_chunk, callback=callback):
                done_event.wait()
            break
        except Exception:
            if channels == ([2, 1] if IS_WINDOWS else [1, 2])[-1]:
                raise
            continue

    if not audio_buffer:
        return None

    audio     = np.concatenate(audio_buffer)
    audio_16k = _resample(audio, native_sr, TARGET_SR)

    if len(audio_16k) / TARGET_SR < MIN_SPEECH_DURATION:
        return None

    return audio_16k