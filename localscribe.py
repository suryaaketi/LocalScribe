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
