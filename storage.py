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

    def settings(self):
        if not self.path.is_file():
            return Settings()
        with closing(self._reader()) as connection:
            return self._read_settings(connection)

    def update_settings(self, settings):
        with closing(self._writer()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._initialize(connection)
            connection.execute(
                "INSERT INTO settings (id, font_size, saves_history) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET font_size = excluded.font_size, "
                "saves_history = excluded.saves_history",
                (settings.font_size, settings.saves_history),
            )
            if not settings.saves_history:
                connection.execute("DELETE FROM transcript_cache")

    def cache_get(self, key):
        if not self.path.is_file():
            return None
        with closing(self._reader()) as connection:
            connection.execute("BEGIN")
            if not self._read_settings(connection).saves_history or not self._has_table(connection, "transcript_cache"):
                return None
            row = connection.execute(
                "SELECT transcripts.text FROM transcript_cache "
                "JOIN transcripts ON transcripts.id = transcript_cache.transcript_id "
                "WHERE transcript_cache.key = ?",
                (key,),
            ).fetchone()
            return row[0] if row else None

    def save(self, text, *, cache_key=None):
        with closing(self._writer()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._initialize(connection)
            if not self._read_settings(connection).saves_history:
                return False
            transcript = connection.execute("INSERT INTO transcripts (text) VALUES (?)", (text,))
            if cache_key is not None:
                connection.execute(
                    "INSERT INTO transcript_cache (key, transcript_id) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET transcript_id = excluded.transcript_id",
                    (cache_key, transcript.lastrowid),
                )
                connection.execute(
                    "DELETE FROM transcript_cache WHERE key IN (SELECT key FROM transcript_cache "
                    "ORDER BY transcript_id DESC LIMIT -1 OFFSET ?)",
                    (CACHE_LIMIT,),
                )
            return True

    def recent(self):
        if not self.path.is_file():
            return []
        with closing(self._reader()) as connection:
            if not self._has_table(connection, "transcripts"):
                return []
            return [
                text for (text,) in connection.execute("SELECT text FROM transcripts ORDER BY id DESC LIMIT 20")
            ]

    def _reader(self):
        return sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)

    def _writer(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _has_table(connection, name):
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone() is not None
