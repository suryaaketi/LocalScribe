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
    viewport = ttk.Frame(body)
    viewport.pack(fill="both", expand=True)
    text = tk.Text(viewport, wrap="word", padx=8, pady=8, font=text_font, state="disabled")
    scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=text.yview)
    scrollbar.pack(side="right", fill="y")
    text.configure(yscrollcommand=scrollbar.set)
    text.pack(side="left", fill="both", expand=True)
    events = Queue()
    busy = False

    def show(value, *, append=False):
        following = text.yview()[1] >= 0.99
        anchor = text.index("@0,0")
        text.configure(state="normal")
        if not append:
            text.delete("1.0", "end")
        text.insert("end", value)
        text.configure(state="disabled")
        text.yview("end" if append and following else anchor if append else "1.0")
