# LocalScribe

LocalScribe is a desktop prototype for offline speech-to-text. Open an English-language WAV file, read the transcript, and find it again in your local history. The same Python entry point detects macOS or Windows at launch and picks that system’s controls, speech engine, and settings folder. The installed Swift Mac app is a separate release.

## Set up on a Windows x64 PC

1. Install [Python 3.11 or later](https://www.python.org/downloads/windows/) with the Python launcher and Tcl/Tk options enabled.
2. Download [whisper.cpp v1.8.3](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.8.3). Start with the CPU `whisper-bin-x64.zip`. Extract it and place `whisper-cli.exe` and its accompanying DLLs together in `.build\engine` under this project. The upstream ZIP’s SHA-256 is `d824b1e37599f882b396e73f1ee0bfd5d0529f700314c48311dcbd00b803321d`.
3. Download [Whisper large-v3 Turbo Q5](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-large-v3-turbo-q5_0.bin) to `.build\models\ggml-large-v3-turbo-q5_0.bin`. Its SHA-256 is `394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2`. The Mac Core ML folder cannot be used here.
