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
