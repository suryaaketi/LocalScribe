"""Windows controls for the offline WAV prototype."""

from dataclasses import replace
from pathlib import Path
from queue import Empty, Queue
import sqlite3
from threading import Thread
import tkinter as tk
from tkinter import filedialog, font, ttk

from storage import MAX_FONT_SIZE, MIN_FONT_SIZE, Settings


def run_windows_app(transcribe, history, display_error, smoke_test=False):
    root = tk.Tk()
    root.title("LocalScribe Control Center")
    root.geometry("760x480")
    root.minsize(540, 320)
    if smoke_test:
        root.withdraw()
    body = ttk.Frame(root, padding=12)
    body.pack(fill="both", expand=True)
    status = tk.StringVar(value="Choose a local WAV file to transcribe.")
    ttk.Label(body, textvariable=status, wraplength=510).pack(side="bottom", anchor="w", pady=(8, 0))
    toolbar = ttk.Frame(body)
    toolbar.pack(fill="x", pady=(0, 8))
    try:
        settings = history.settings()
    except (OSError, sqlite3.Error):
        settings = Settings()
        status.set("Local settings are unavailable. Check the app’s storage and try again.")
    saves_history = tk.BooleanVar(value=settings.saves_history)
    text_font = font.nametofont("TkDefaultFont").copy()
    text_font.configure(size=settings.font_size)
