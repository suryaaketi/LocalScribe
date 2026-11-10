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


def transcribe(audio, engine, model, on_partial=None):
    try:
        source = wave.open(str(audio), "rb")
    except (wave.Error, EOFError):
        # The native engine may decode WAV encodings the standard Python reader cannot.
        return transcribe_section(audio, engine, model)

    with source:
        frames = source.getnframes()
        section_frames = source.getframerate() * SECTION_SECONDS
        if frames <= section_frames:
            return transcribe_section(audio, engine, model)
        count = (frames + section_frames - 1) // section_frames
        pieces = []
        with tempfile.TemporaryDirectory(prefix="localscribe-audio-section-") as scratch:
            section = Path(scratch) / "section.wav"
            for index in range(count):
                write_wave_section(source, section, min(section_frames, frames - index * section_frames))
                try:
                    text = transcribe_section(section, engine, model)
                except NoSpeech:
                    text = ""
                if text:
                    pieces.append(text)
                if on_partial is not None:
                    on_partial(text, index + 1, count)
        if not pieces:
            raise NoSpeech()
        return "\n\n".join(pieces)


def file_stamp(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def cache_key(audio, engine, model):
    # Use model file metadata so cache lookups do not read gigabytes of weights.
    if WINDOWS:
        assets = {model, *engine.parent.glob("*.dll")}
    else:
        assets = set(model.glob("*.mlmodelc/coremldata.bin"))
        assets.update(model.glob("*.mlmodelc/model.mil"))
        assets.update(model.glob("*.mlmodelc/weights/*.bin"))
        assets.update(model / name for name in REQUIRED_MODEL_FILES)
    stamps = [file_stamp(path) for path in sorted(assets)]
    with audio.open("rb") as stream:
        audio_digest = file_digest(stream, "sha256").hexdigest()
    cache_version = "localscribe-whisper-cpp-v1" if WINDOWS else "localscribe-transcript-v2"
    identity = [cache_version, SECTION_SECONDS, audio_digest, file_stamp(engine), stamps]
    return sha256(json.dumps(identity).encode()).hexdigest()


def process_audio(audio, engine, model, history, on_partial=None):
    check_setup(engine, model)
    if not audio.is_file() or audio.suffix.lower() != ".wav":
        raise LocalScribeError("Choose a local WAV audio file.")
    try:
        saves_history = history.settings().saves_history
        stamp = file_stamp(audio)
        key = cache_key(audio, engine, model) if saves_history else None
        if key and file_stamp(audio) == stamp:
            cached = history.cache_get(key)
            if cached is not None:
                return cached, "Loaded from local transcript cache."
    except (OSError, sqlite3.Error):
        return transcribe(audio, engine, model, on_partial), "Transcript ready. Local history was unavailable."

    text = transcribe(audio, engine, model, on_partial)
    if saves_history:
        try:
            valid_key = key if file_stamp(audio) == stamp else None
            if history.save(text, cache_key=valid_key):
                return text, "Saved to local history."
        except (OSError, sqlite3.Error):
            return text, "Transcript ready. Local history could not be saved."
    return text, "Transcript ready. History saving is off."


def run_mac_app(engine, model, history, smoke_test):
    import AppKit as mac
    import objc
    from Foundation import NSObject
    from PyObjCTools import AppHelper

    class Face(mac.NSView):
        def drawRect_(self, _):
            mac.NSColor.blackColor().setFill()
            mac.NSBezierPath.bezierPathWithOvalInRect_(self.bounds()).fill()
            mac.NSColor.whiteColor().setFill()
            for x in (20, 35):
                eye = mac.NSMakeRect(x, 26, 8, 13)
                mac.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(eye, 4, 4).fill()

        @objc.python_method
        def pressFeedback(self, opacity):
            if mac.NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion():
                self.setAlphaValue_(opacity)
                return
            mac.NSAnimationContext.beginGrouping()
            mac.NSAnimationContext.currentContext().setDuration_(0.12)
            self.animator().setAlphaValue_(opacity)
            mac.NSAnimationContext.endGrouping()

        def mouseDown_(self, event):
            self.press = self.window().mouseLocationOutsideOfEventStream()
            self.dragged = False
            self.pressFeedback(0.75)

        def mouseDragged_(self, event):
            point = mac.NSEvent.mouseLocation()
            proposed = mac.NSMakePoint(point.x - self.press.x, point.y - self.press.y)
            origin = self.window().frame().origin
            if self.dragged or abs(proposed.x - origin.x) + abs(proposed.y - origin.y) >= 4:
                self.dragged = True
                self.window().setFrameOrigin_(proposed)

        def mouseUp_(self, event):
            self.pressFeedback(1)

    class Controls(NSObject):
        @objc.python_method
        def prepare(self):
            self.busy = False
            self.ready = False
            self.user_resized = False
            self.fitting = False
            self.settings = Settings()
            self.window = mac.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                mac.NSMakeRect(0, 0, 640, 425),
                mac.NSWindowStyleMaskTitled | mac.NSWindowStyleMaskClosable | mac.NSWindowStyleMaskResizable,
                mac.NSBackingStoreBuffered, False,
            )
            self.window.setTitle_("LocalScribe")
            self.window.setMinSize_(mac.NSMakeSize(515, 390))
            self.window.setReleasedWhenClosed_(False)
            self.window.center()

            title = mac.NSTextField.labelWithString_("Transcribe a WAV file")
            title.setFont_(mac.NSFont.systemFontOfSize_weight_(23, mac.NSFontWeightSemibold))
            intro = mac.NSTextField.wrappingLabelWithString_("Choose a WAV with English speech. Your transcript appears below.")
            intro.setFont_(mac.NSFont.systemFontOfSize_(15))
            intro.setTextColor_(mac.NSColor.secondaryLabelColor())
            self.button = self.makeButton("Choose WAV File…", "chooseAudio:")
            self.history_button = self.makeButton("Show History", "showHistory:")
            actions = self.makeRow([self.button, self.history_button])

            self.save_history = mac.NSButton.checkboxWithTitle_target_action_("Save transcript history", self, "saveHistory:")
            self.save_history.setFont_(mac.NSFont.systemFontOfSize_(14))
            smaller = self.makeButton("Smaller Text", "changeTextSize:")
            smaller.setTag_(-1)
            larger = self.makeButton("Larger Text", "changeTextSize:")
            larger.setTag_(1)
            settings = self.makeRow([self.save_history, smaller, larger])

            self.status = mac.NSTextField.wrappingLabelWithString_("Ready for offline transcription.")
            self.status.setFont_(mac.NSFont.systemFontOfSize_(14))
            self.status.setTextColor_(mac.NSColor.secondaryLabelColor())
            self.scroll = mac.NSScrollView.alloc().initWithFrame_(mac.NSMakeRect(0, 0, 600, 190))
            self.scroll.setHasVerticalScroller_(True)
            self.scroll.setScrollerStyle_(mac.NSScrollerStyleLegacy)
            self.scroll.setAutohidesScrollers_(False)
            self.scroll.setBorderType_(mac.NSBezelBorder)
            self.text = mac.NSTextView.alloc().initWithFrame_(self.scroll.contentView().bounds())
            self.text.setEditable_(False)
            self.text.setSelectable_(True)
            self.text.setVerticallyResizable_(True)
            self.text.setHorizontallyResizable_(False)
            self.text.setMinSize_(mac.NSMakeSize(0, 0))
            self.text.setMaxSize_(mac.NSMakeSize(10_000_000, 10_000_000))
            self.text.setAutoresizingMask_(mac.NSViewWidthSizable)
            container = self.text.textContainer()
            container.setContainerSize_(mac.NSMakeSize(600, 10_000_000))
            container.setWidthTracksTextView_(True)
            container.setHeightTracksTextView_(False)
            self.text.setTextContainerInset_(mac.NSMakeSize(10, 9))
            self.text.setBackgroundColor_(mac.NSColor.textBackgroundColor())
            self.scroll.setDocumentView_(self.text)

            content = self.window.contentView()
            stack = mac.NSStackView.stackViewWithViews_([title, intro, actions, settings, self.status, self.scroll])
            stack.setOrientation_(mac.NSUserInterfaceLayoutOrientationVertical)
            stack.setAlignment_(mac.NSLayoutAttributeLeading)
            stack.setSpacing_(8)
            stack.setTranslatesAutoresizingMaskIntoConstraints_(False)
            content.addSubview_(stack)
            mac.NSLayoutConstraint.activateConstraints_([
                stack.leadingAnchor().constraintEqualToAnchor_constant_(content.leadingAnchor(), 18),
                stack.trailingAnchor().constraintEqualToAnchor_constant_(content.trailingAnchor(), -18),
                stack.topAnchor().constraintEqualToAnchor_constant_(content.topAnchor(), 16),
                stack.bottomAnchor().constraintEqualToAnchor_constant_(content.bottomAnchor(), -16),
                intro.widthAnchor().constraintEqualToAnchor_(stack.widthAnchor()),
                self.status.widthAnchor().constraintEqualToAnchor_(stack.widthAnchor()),
                self.scroll.widthAnchor().constraintEqualToAnchor_(stack.widthAnchor()),
                self.scroll.heightAnchor().constraintGreaterThanOrEqualToConstant_(120),
            ])
            for label in (title, intro, self.status):
                label.setContentHuggingPriority_forOrientation_(751, mac.NSLayoutConstraintOrientationVertical)
                label.setContentCompressionResistancePriority_forOrientation_(751, mac.NSLayoutConstraintOrientationVertical)

            self.window.setDelegate_(self)
            try:
                self.settings = history.settings()
                self.loadHistory()
            except (OSError, sqlite3.Error):
                self.showText("Your transcript will appear here after you choose a WAV file.")
                self.status.setStringValue_("Local history is unavailable. Check the app’s storage and try again.")
            self.applySettings()

            try:
                check_setup(engine, model)
            except LocalScribeError as error:
                self.status.setStringValue_(str(error))
                self.button.setEnabled_(False)
            else:
                self.ready = True
                self.window.setInitialFirstResponder_(self.button)
                self.window.setDefaultButtonCell_(self.button.cell())

            frame = mac.NSMakeRect(0, 0, 64, 64)
            self.pet = mac.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, mac.NSWindowStyleMaskBorderless | mac.NSWindowStyleMaskNonactivatingPanel,
                mac.NSBackingStoreBuffered, False,
            )
            self.pet.setTitle_("LocalScribe Pet")
            self.pet.setOpaque_(False)
            self.pet.setBackgroundColor_(mac.NSColor.clearColor())
            self.pet.setHasShadow_(False)
            self.pet.setFloatingPanel_(True)
            self.pet.setLevel_(mac.NSFloatingWindowLevel)
            self.pet.setHidesOnDeactivate_(False)
            self.pet.setContentView_(Face.alloc().initWithFrame_(frame))
            screen = mac.NSScreen.mainScreen()
            if screen:
                area = screen.visibleFrame()
                self.pet.setFrameOrigin_(mac.NSMakePoint(
                    area.origin.x + area.size.width - 90, area.origin.y + 56
                ))

        @objc.python_method
        def makeButton(self, title, action):
            button = mac.NSButton.buttonWithTitle_target_action_(title, self, action)
            button.setControlSize_(mac.NSControlSizeLarge)
            button.setFont_(mac.NSFont.systemFontOfSize_(14))
            button.heightAnchor().constraintGreaterThanOrEqualToConstant_(40).setActive_(True)
            return button

        @objc.python_method
        def makeRow(self, views):
            row = mac.NSStackView.stackViewWithViews_(views)
            row.setOrientation_(mac.NSUserInterfaceLayoutOrientationHorizontal)
            row.setAlignment_(mac.NSLayoutAttributeCenterY)
            row.setSpacing_(8)
            return row

        @objc.python_method
        def showText(self, text, expand=False):
            self.text.setString_(text)
            self.text.setFont_(mac.NSFont.systemFontOfSize_(self.settings.font_size))
            self.text.setTextColor_(mac.NSColor.textColor())
            self.fitTranscript(expand)
            self.text.scrollRangeToVisible_((0, 0))

        @objc.python_method
        def transcriptHeight(self):
            self.window.contentView().layoutSubtreeIfNeeded()
            size = self.scroll.contentView().bounds().size
            self.text.setFrameSize_(mac.NSMakeSize(size.width, self.text.frame().size.height))
            container = self.text.textContainer()
            layout = self.text.layoutManager()
            layout.ensureLayoutForTextContainer_(container)
            used = layout.usedRectForTextContainer_(container)
            return ceil(mac.NSMaxY(used) + 2 * self.text.textContainerInset().height)

        @objc.python_method
        def fitTranscript(self, expand=False):
            if self.fitting:
                return
            self.fitting = True
            try:
                height = self.transcriptHeight()
                clip = self.scroll.contentView()
                if expand and not self.user_resized:
                    screen = self.window.screen() or mac.NSScreen.mainScreen()
                    if screen:
                        area = screen.visibleFrame()
                        frame = self.window.frame()
                        available = max(0, area.size.height - 24 - frame.size.height)
                        grow = min(available, max(0, height - clip.bounds().size.height))
                        if grow > 0:
                            new_height = frame.size.height + grow
                            top = min(mac.NSMaxY(area) - 12, max(mac.NSMaxY(frame), area.origin.y + 12 + new_height))
                            self.window.setFrame_display_(mac.NSMakeRect(
                                frame.origin.x, top - new_height, frame.size.width, new_height
                            ), True)
                            height = self.transcriptHeight()
                size = clip.bounds().size
                self.text.setFrameSize_(mac.NSMakeSize(size.width, max(size.height, height)))
                self.scroll.reflectScrolledClipView_(clip)
            finally:
                self.fitting = False

        def windowWillStartLiveResize_(self, _):
            self.user_resized = True

        def windowDidResize_(self, _):
            self.fitTranscript()

        @objc.python_method
        def appendTranscript(self, text, section, total):
            self.status.setStringValue_(f"Transcribing on this Mac… {section} of {total} sections ready.")
            if not text:
                return
            clip = self.scroll.contentView()
            bounds = clip.bounds()
            at_bottom = mac.NSMaxY(bounds) >= self.text.frame().size.height - 24
            storage = self.text.textStorage()
            prefix = "\n\n" if storage.length() else ""
            attributes = {
                mac.NSFontAttributeName: mac.NSFont.systemFontOfSize_(self.settings.font_size),
                mac.NSForegroundColorAttributeName: mac.NSColor.textColor(),
            }
            storage.appendAttributedString_(mac.NSAttributedString.alloc().initWithString_attributes_(prefix + text, attributes))
            self.fitTranscript(expand=True)
            if at_bottom:
                self.text.scrollRangeToVisible_((storage.length(), 0))
            else:
                clip.scrollToPoint_(bounds.origin)
                self.scroll.reflectScrolledClipView_(clip)

        @objc.python_method
        def loadHistory(self):
            entries = history.recent()
            self.showText("\n\n".join(entries) if entries else
                          "Your transcript will appear here after you choose a WAV file.")

        @objc.python_method
        def applySettings(self, expand=False):
            self.text.setFont_(mac.NSFont.systemFontOfSize_(self.settings.font_size))
            self.save_history.setState_(mac.NSControlStateValueOn if self.settings.saves_history else mac.NSControlStateValueOff)
            self.fitTranscript(expand)

        @objc.python_method
        def updateSettings(self, settings):
            try:
                history.update_settings(settings)
                self.settings = settings
            except (OSError, sqlite3.Error):
                self.status.setStringValue_("Couldn’t save your settings. Check the app’s storage and try again.")
            self.applySettings(expand=True)

        def changeTextSize_(self, sender):
            size = min(MAX_FONT_SIZE, max(MIN_FONT_SIZE, self.settings.font_size + sender.tag()))
            self.updateSettings(replace(self.settings, font_size=size))

        def saveHistory_(self, sender):
            if not self.busy:
                self.updateSettings(replace(self.settings, saves_history=sender.state() == mac.NSControlStateValueOn))

        def showHistory_(self, _):
            if self.busy:
                return
            try:
                self.loadHistory()
            except (OSError, sqlite3.Error):
                self.status.setStringValue_("Couldn’t open saved transcripts. Check the app’s storage and try again.")

        @objc.python_method
        def setBusy(self, busy):
            self.busy = busy
            self.button.setEnabled_(self.ready and not busy)
            self.save_history.setEnabled_(not busy)
            self.history_button.setEnabled_(not busy)

        def chooseAudio_(self, _):
            if self.busy or not self.ready:
                return
            self.setBusy(True)
            panel = mac.NSOpenPanel.openPanel()
            panel.setAllowsMultipleSelection_(False)
            panel.setAllowedFileTypes_(["wav"])
            if panel.runModal() != mac.NSModalResponseOK or panel.URL() is None:
                self.setBusy(False)
                return
            audio = Path(panel.URL().path()).resolve()
            self.showText("")
            self.status.setStringValue_("Transcribing on this Mac…")
            Thread(target=self.transcribe_in_background, args=(audio,), daemon=True).start()

        @objc.python_method
        def transcribe_in_background(self, audio):
            try:
                def preview(text, section, total):
                    AppHelper.callAfter(self.appendTranscript, text, section, total)

                text, status = process_audio(audio, engine, model, history, preview)
                AppHelper.callAfter(self.finished, text, status)
            except (OSError, LocalScribeError) as error:
                AppHelper.callAfter(self.finished, None, display_error(error))

        @objc.python_method
        def finished(self, text, status):
            if text is not None and self.text.string() != text:
                self.showText(text, expand=True)
            elif text is None and self.text.string():
                status = "Partial transcript shown. " + status
            elif text is None:
                self.showText("Choose another WAV file to try again.")
            self.status.setStringValue_(status)
            self.setBusy(False)

    application = mac.NSApplication.sharedApplication()
    application.setActivationPolicy_(mac.NSApplicationActivationPolicyRegular)
    controls = Controls.alloc().init()
    controls.prepare()
    if smoke_test:
        assert controls.window.title() == "LocalScribe"
        assert controls.pet.frame().size.width == 64
        assert controls.text.string().strip()
        if controls.ready:
            assert controls.window.initialFirstResponder() == controls.button
            assert controls.window.defaultButtonCell() == controls.button.cell()
            controls.setBusy(True)
            controls.chooseAudio_(None)
            assert controls.busy and not controls.button.isEnabled()
            controls.setBusy(False)
            assert controls.button.isEnabled()
        controls.settings = replace(controls.settings, font_size=MAX_FONT_SIZE)
        controls.applySettings()
        assert controls.text.font().pointSize() == MAX_FONT_SIZE
        for appearance in (mac.NSAppearanceNameAqua, mac.NSAppearanceNameDarkAqua):
            controls.window.setAppearance_(mac.NSAppearance.appearanceNamed_(appearance))
            controls.window.setContentSize_(mac.NSMakeSize(515, 390))
            controls.window.contentView().layoutSubtreeIfNeeded()
            assert controls.button.frame().size.height >= 40
            assert controls.scroll.frame().size.height >= 120
        controls.showText("")
        original = controls.window.frame()
        controls.appendTranscript("The first section is ready.\n" * 110, 1, 4)
        clip = controls.scroll.contentView()
        assert controls.text.frame().size.height > clip.bounds().size.height
        assert controls.scroll.scrollerStyle() == mac.NSScrollerStyleLegacy
        assert controls.scroll.hasVerticalScroller() and not controls.scroll.autohidesScrollers()
        screen = controls.window.screen() or mac.NSScreen.mainScreen()
        if screen and screen.visibleFrame().size.height > original.size.height + 24:
            assert controls.window.frame().size.height > original.size.height
            assert controls.window.frame().size.height <= screen.visibleFrame().size.height
        clip.scrollToPoint_(mac.NSMakePoint(0, 120))
        controls.scroll.reflectScrolledClipView_(clip)
        origin = clip.bounds().origin.y
        controls.appendTranscript("More text without moving the reader.\n" * 40, 2, 4)
        assert abs(clip.bounds().origin.y - origin) < 2
        controls.windowWillStartLiveResize_(None)
        controls.window.setContentSize_(mac.NSMakeSize(550, 400))
        controls.windowDidResize_(None)
        resized = controls.window.frame().size.height
        last_origin = controls.text.frame().size.height - clip.bounds().size.height
        clip.scrollToPoint_(mac.NSMakePoint(0, last_origin))
        controls.scroll.reflectScrolledClipView_(clip)
        controls.appendTranscript("The viewport follows the end.\n" * 45, 3, 4)
        assert controls.window.frame().size.height == resized
        assert clip.bounds().origin.y > last_origin
        assert controls.text.frame().size.height - mac.NSMaxY(clip.bounds()) <= 24
        reading = clip.bounds().origin.y
        controls.finished(controls.text.string(), "Saved to local history.")
        assert abs(clip.bounds().origin.y - reading) < 2
        transcript = controls.text.string()
        controls.finished(None, "The final section failed.")
        assert controls.text.string() == transcript
        assert controls.status.stringValue().startswith("Partial transcript shown.")
        print("PASS: light/dark, resize, screen-bounded growth, scroll position, and end following")
        return

    menu_bar = mac.NSMenu.alloc().init()
    root = mac.NSMenuItem.alloc().init()
    menu = mac.NSMenu.alloc().initWithTitle_("LocalScribe")
    menu.addItemWithTitle_action_keyEquivalent_("Quit LocalScribe", "terminate:", "q")
    root.setSubmenu_(menu)
    menu_bar.addItem_(root)
    file_item = mac.NSMenuItem.alloc().init()
    file_menu = mac.NSMenu.alloc().initWithTitle_("File")
    open_item = file_menu.addItemWithTitle_action_keyEquivalent_("Choose WAV File…", "chooseAudio:", "o")
    open_item.setTarget_(controls)
    file_item.setSubmenu_(file_menu)
    menu_bar.addItem_(file_item)
    application.setMainMenu_(menu_bar)
    controls.window.makeKeyAndOrderFront_(None)
    controls.pet.orderFrontRegardless()
    application.activateIgnoringOtherApps_(True)
    AppHelper.runEventLoop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=Path(os.environ.get("LOCALSCRIBE_ENGINE", DEFAULT_ENGINE)))
    parser.add_argument("--model", type=Path, default=Path(os.environ.get("LOCALSCRIBE_MODEL", DEFAULT_MODEL)))
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--smoke-test", action="store_true", help="Check desktop controls without loading the speech engine.")
    modes.add_argument("--check-setup", action="store_true", help="Check local engine and model files.")
    modes.add_argument("--transcribe-file", type=Path)
    args = parser.parse_args()
    if sys.platform not in {"darwin", "win32"}:
        parser.exit(1, "This LocalScribe prototype supports macOS and Windows.\n")
    history = History(args.state_dir.expanduser().resolve())
    engine = args.engine.expanduser().resolve()
    model = args.model.expanduser().resolve()
    if args.check_setup:
        try:
            check_setup(engine, model)
        except LocalScribeError as error:
            parser.exit(1, f"{error}\n")
        print("Local engine and model files are available.")
    elif args.transcribe_file:
        try:
            text, _ = process_audio(args.transcribe_file.expanduser().resolve(), engine, model, history)
        except (OSError, LocalScribeError) as error:
            parser.exit(1, f"{display_error(error)}\n")
        print(text)
    elif WINDOWS:
        from functools import partial
        try:
            from windows_app import run_windows_app
        except ModuleNotFoundError as error:
            if error.name not in {"tkinter", "_tkinter"}:
                raise
            parser.exit(1, "Install Python with the Tcl/Tk option to open the LocalScribe window.\n")

        run_windows_app(partial(process_audio, engine=engine, model=model, history=history),
                        history, display_error, args.smoke_test)
    else:
        run_mac_app(engine, model, history, args.smoke_test)


if __name__ == "__main__":
    main()
