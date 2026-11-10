"""Local SQLite storage for transcript history, settings, and cache keys."""

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3


MIN_FONT_SIZE = 12
MAX_FONT_SIZE = 28
CACHE_LIMIT = 32
