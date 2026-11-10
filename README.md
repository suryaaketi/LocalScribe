# LocalScribe

LocalScribe is a desktop prototype for offline speech-to-text. Open an English-language WAV file, read the transcript, and find it again in your local history. The same Python entry point detects macOS or Windows at launch and picks that system’s controls, speech engine, and settings folder. The installed Swift Mac app is a separate release.

## Set up on a Windows x64 PC

1. Install [Python 3.11 or later](https://www.python.org/downloads/windows/) with the Python launcher and Tcl/Tk options enabled.
2. Download [whisper.cpp v1.8.3](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.8.3). Start with the CPU `whisper-bin-x64.zip`. Extract it and place `whisper-cli.exe` and its accompanying DLLs together in `.build\engine` under this project. The upstream ZIP’s SHA-256 is `d824b1e37599f882b396e73f1ee0bfd5d0529f700314c48311dcbd00b803321d`.
3. Download [Whisper large-v3 Turbo Q5](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-large-v3-turbo-q5_0.bin) to `.build\models\ggml-large-v3-turbo-q5_0.bin`. Its SHA-256 is `394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2`. The Mac Core ML folder cannot be used here.
4. Open **Run LocalScribe Windows.cmd**, then choose **Transcribe WAV…** or press **Ctrl–O**. Start with a 16-bit PCM WAV. The Windows control window is resizable and includes a transcript scrollbar, text-size controls, and local history.

From PowerShell in the project folder, you can check the files and the controls or run a command-line transcription.

```powershell
py -3 .\localscribe.py --check-setup
py -3 .\localscribe.py --smoke-test
py -3 .\localscribe.py --transcribe-file 'C:\path\to\sample.wav'
```

Use `--engine` or `LOCALSCRIBE_ENGINE` to choose an alternate local Windows build, including one built with CUDA. Use `--model` or `LOCALSCRIBE_MODEL` to choose another local Whisper model in ggml format. The Windows prototype stores its settings and history under `%LOCALAPPDATA%\LocalScribe Python Prototype`.

## Set up on an Apple Silicon Mac

Use Python 3.11 or later, Git, and Xcode with the macOS SDK. Development was verified with Python 3.11 and Xcode 27.2. Run these commands from the project directory.

```sh
python3 -m venv .build/venv
.build/venv/bin/python -m pip install -r requirements.txt
./setup_engine.sh
```

### Get the speech assets

Download the Core ML weights from Argmax and the matching tokenizer from OpenAI. The model folder is about 1.64 GB. These commands fetch the selected model and tokenizer at fixed revisions. You can also use an existing copy with `LOCALSCRIBE_MODEL` or `--model`.

```sh
.build/venv/bin/python -m pip install 'huggingface_hub==1.33.0'
HF_HUB_DISABLE_IMPLICIT_TOKEN=1 .build/venv/bin/hf download argmaxinc/whisperkit-coreml \
  --revision 04e5c42d80a522518023727e8c7e68d4bb391b28 \
  --include 'openai_whisper-large-v3-v20240930_turbo/**' \
  --local-dir .build/models
HF_HUB_DISABLE_IMPLICIT_TOKEN=1 .build/venv/bin/hf download openai/whisper-large-v3 \
  config.json tokenizer.json tokenizer_config.json \
  --revision 06f233fe06e710322aca913c1bc4249a0d71fce1 \
  --local-dir .build/models/openai_whisper-large-v3-v20240930_turbo/tokenizer
```

### Run LocalScribe

Double-click `Run LocalScribe Python.command` or run it from Terminal. Choose **Transcribe a WAV File**. A setup check and command-line transcription are also available.

```sh
"./Run LocalScribe Python.command" --check-setup
"./Run LocalScribe Python.command" --smoke-test
"./Run LocalScribe Python.command" --transcribe-file /path/to/example.wav
```

For long PCM WAV files, LocalScribe displays each completed minute of source audio as it finishes processing. The window can grow within the screen's usable area, then the transcript scrolls. Drag a window edge to choose your own size. If you scroll up, new text leaves your reading position alone. Scroll back to the bottom to follow incoming text. WAV encodings that need Core Audio's decoder display the result when processing finishes.

Press **Command–O** to choose a file. **Smaller Text** and **Larger Text** change the transcript size and remember it for the next launch. **Show History** opens the recent saved transcripts.

Use `--engine` or `LOCALSCRIBE_ENGINE` to select another local Argmax CLI. Use `--state-dir` to test with a separate history directory.

## Privacy and current scope

Setup downloads source, dependencies, and model assets from their publishers. The app passes a local WAV and model to the engine and makes no network requests during transcription. The Mac prototype additionally denies network access to its engine process. LocalScribe leaves the WAV in place. It keeps preferences and, when enabled, transcript text, timestamps, and up to 32 cache keys in a local SQLite database. On macOS the database is under `~/Library/Application Support/LocalScribe Python Prototype`. Settings and history stay on the device where they were saved. Reopening the same WAV with the same engine and model can reuse a saved transcript. Turning off history saving clears the cache keys and stops new saves. You can still open previously saved transcripts.

The prototype supports WAV transcription and text history. Live microphone and system audio capture, the global shortcut, automatic paste, and installers are pending. The Windows window is the first porting step. The floating pet is currently available in the Mac prototype and installed Mac app.

## Credits

OpenAI developed Whisper. Argmax converted the large-v3 Turbo model to Core ML and publishes the WhisperKit engine used by this project. PyObjC connects the Python app to Apple’s native macOS frameworks. See [third-party sources and licenses](THIRD_PARTY_NOTICES.md).

LocalScribe’s own source is available under the [MIT license](LICENSE).
