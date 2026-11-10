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
