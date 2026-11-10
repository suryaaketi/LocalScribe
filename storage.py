"""Local SQLite storage for transcript history, settings, and cache keys."""

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3


MIN_FONT_SIZE = 12
MAX_FONT_SIZE = 28
CACHE_LIMIT = 32


@dataclass(frozen=True)
class Settings:
    font_size: int = 15
    saves_history: bool = True

    def __post_init__(self):
        if type(self.font_size) is not int or not MIN_FONT_SIZE <= self.font_size <= MAX_FONT_SIZE:
            raise ValueError(f"Text size must be between {MIN_FONT_SIZE} and {MAX_FONT_SIZE} points.")
        if type(self.saves_history) is not bool:
            raise ValueError("Choose whether to save history.")


class History:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.path = self.directory / "history.sqlite3"
