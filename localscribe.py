"""LocalScribe, a desktop prototype for offline WAV transcription."""

import argparse
from dataclasses import replace
from hashlib import file_digest, sha256
import json
from math import ceil
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from threading import Thread
import wave

from storage import MAX_FONT_SIZE, MIN_FONT_SIZE, History, Settings


PROJECT_DIR = Path(__file__).resolve().parent
WINDOWS = sys.platform == "win32"
if WINDOWS:
    DEFAULT_ENGINE = PROJECT_DIR / ".build/engine/whisper-cli.exe"
    DEFAULT_MODEL = PROJECT_DIR / ".build/models/ggml-large-v3-turbo-q5_0.bin"
    DEFAULT_STATE_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "LocalScribe Python Prototype"
else:
    DEFAULT_ENGINE = PROJECT_DIR / ".build/engine/argmax-cli"
    DEFAULT_MODEL = PROJECT_DIR / ".build/models/openai_whisper-large-v3-v20240930_turbo"
    DEFAULT_STATE_DIR = Path.home() / "Library/Application Support/LocalScribe Python Prototype"
SECTION_SECONDS = 60

REQUIRED_MODEL_FILES = (
    "config.json",
    "generation_config.json",
    "AudioEncoder.mlmodelc/coremldata.bin",
    "MelSpectrogram.mlmodelc/coremldata.bin",
    "TextDecoder.mlmodelc/coremldata.bin",
    "tokenizer/config.json",
    "tokenizer/tokenizer.json",
    "tokenizer/tokenizer_config.json",
)


class LocalScribeError(ValueError):
    """An error message safe to show to a user."""


class NoSpeech(LocalScribeError):
    def __init__(self):
        super().__init__("No speech was detected. Try a WAV file with clear speech.")


def display_error(error):
    if isinstance(error, LocalScribeError):
        return str(error)
    return "LocalScribe couldn’t read the file or run the speech engine. Check the setup and try again."


def check_setup(engine, model):
    if WINDOWS:
        if engine.suffix.lower() != ".exe" or not engine.is_file():
            raise LocalScribeError("Install whisper-cli.exe for Windows or select it with --engine. See the README.")
        if not model.is_file():
            raise LocalScribeError("The Windows speech model is missing. See the README or select a model with --model.")
        return
    if not engine.is_file() or not os.access(engine, os.X_OK):
        raise LocalScribeError("The Argmax CLI is missing. Run setup_engine.sh or pass --engine.")
    for name in REQUIRED_MODEL_FILES:
        if not (model / name).is_file():
            raise LocalScribeError(f"The local speech model is missing {name}. See the README for setup.")


def transcribe_section(audio, engine, model):
    """Run the platform’s local engine on one section."""
    if WINDOWS:
        return transcribe_windows_section(audio, engine, model)
    tokenizer = model / "tokenizer"
    with tempfile.TemporaryDirectory(prefix="localscribe-python-report-") as output:
        command = [
            "/usr/bin/sandbox-exec", "-p", "(version 1) (allow default) (deny network*)",
            str(engine), "transcribe",
            "--audio-path", str(audio), "--model-path", str(model),
            "--download-tokenizer-path", str(tokenizer),
            "--audio-encoder-compute-units", "cpuAndGPU",
            "--text-decoder-compute-units", "cpuAndGPU",
            "--language", "en", "--temperature", "0", "--temperature-fallback-count", "0",
            "--use-prefill-prompt", "--skip-special-tokens", "--first-token-log-prob-threshold=-1.5",
            "--chunking-strategy", "none",
            "--report", "--report-path", output,
        ]
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=240, check=False)
        except subprocess.TimeoutExpired:
            raise LocalScribeError("The speech engine timed out. Try a shorter WAV file.") from None
        report = Path(output) / (audio.stem + ".json")
        if result.returncode or not report.is_file():
            raise LocalScribeError("The speech engine couldn’t read this WAV file. Try another file or check the setup.")
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except ValueError:
            raise LocalScribeError("The speech engine returned an unreadable result. Try the file again.") from None
        text = data.get("text") if isinstance(data, dict) else None
        if not isinstance(text, str):
            raise LocalScribeError("The speech engine returned an unreadable result. Try the file again.")
        if not text.strip():
            raise NoSpeech()
        return text.strip()


def transcribe_windows_section(audio, engine, model):
    with tempfile.TemporaryDirectory(prefix="localscribe-python-report-") as output:
        report = Path(output) / "transcript.json"
        command = [str(engine), "-m", str(model), "-f", str(audio), "-l", "en", "-oj", "-of", str(report.with_suffix(""))]
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=240, check=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired:
            raise LocalScribeError("The speech engine timed out. Try a shorter WAV file.") from None
        if result.returncode or not report.is_file():
            raise LocalScribeError("The Windows speech engine couldn’t read the WAV. Check the engine, its DLLs, and the model.")
        try:
            segments = json.loads(report.read_text(encoding="utf-8"))["transcription"]
            if not isinstance(segments, list):
                raise ValueError
            text = " ".join(segment["text"].strip() for segment in segments).strip()
        except (ValueError, KeyError, TypeError, AttributeError):
            raise LocalScribeError("The speech engine returned an unreadable result. Try the file again.") from None
        if not text:
            raise NoSpeech()
        return text


def write_wave_section(source, destination, frames):
    params = source.getparams()
    with wave.open(str(destination), "wb") as output:
        output.setparams(params._replace(nframes=0))
        remaining = frames
        frame_size = params.nchannels * params.sampwidth
        while remaining:
            data = source.readframes(min(remaining, params.framerate))
            if not data or len(data) % frame_size:
                raise LocalScribeError("The WAV ended before all of its audio could be read.")
            output.writeframesraw(data)
            remaining -= len(data) // frame_size
