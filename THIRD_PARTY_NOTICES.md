# Third-party sources

| Component | How LocalScribe uses it | Source and license |
| --- | --- | --- |
| Argmax Open-Source SDK and WhisperKit | Builds the external `argmax-cli` speech engine from revision `dcf3a00f0ae4d5b57bc0aad92063b102b70d5fd1` | [Argmax source and MIT license](https://github.com/argmaxinc/argmax-oss-swift/tree/dcf3a00f0ae4d5b57bc0aad92063b102b70d5fd1), [upstream notices](https://github.com/argmaxinc/argmax-oss-swift/blob/dcf3a00f0ae4d5b57bc0aad92063b102b70d5fd1/NOTICES) |
| Swift Argument Parser 1.8.2 | Parses arguments inside the Argmax CLI | [Apple source license, Apache 2.0 with the Swift Runtime Library Exception](https://github.com/apple/swift-argument-parser/blob/6a52f3251125d74daf04fcbd5e6f08a75d074382/LICENSE.txt) |
| OpenAI Whisper large-v3 Turbo, Argmax Core ML conversion | Local speech recognition model. The selected variant is `openai_whisper-large-v3-v20240930_turbo`. | [OpenAI model card](https://huggingface.co/openai/whisper-large-v3-turbo), [Argmax Core ML model, MIT](https://huggingface.co/argmaxinc/whisperkit-coreml/tree/04e5c42d80a522518023727e8c7e68d4bb391b28/openai_whisper-large-v3-v20240930_turbo) |
| OpenAI Whisper large-v3 tokenizer | Converts between text and model tokens. Setup downloads three configuration and tokenizer files. | [Tokenizer repository, Apache 2.0](https://huggingface.co/openai/whisper-large-v3/tree/06f233fe06e710322aca913c1bc4249a0d71fce1) |
| PyObjC 13.0 | Python bindings for AppKit and Foundation | [PyObjC Core, MIT](https://pypi.org/project/pyobjc-core/13.0/), [PyObjC Cocoa bindings, MIT](https://pypi.org/project/pyobjc-framework-Cocoa/13.0/) |
| Apple AppKit, Foundation, and Core ML | Native windows and controls, system support, and model inference | [AppKit](https://developer.apple.com/documentation/appkit), [Foundation](https://developer.apple.com/documentation/foundation), [Core ML](https://developer.apple.com/documentation/coreml) |
| whisper.cpp v1.8.3 | External offline speech engine on Windows | [Source and MIT license](https://github.com/ggml-org/whisper.cpp/blob/v1.8.3/LICENSE), [release binaries](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.8.3) |
| Whisper large-v3 Turbo Q5, ggml conversion | Windows model asset | [Model and license](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-large-v3-turbo-q5_0.bin) |
| Tkinter and Tcl/Tk | Windows prototype controls, supplied with Python’s Windows installer | [Tkinter documentation](https://docs.python.org/3/library/tkinter.html), [Tcl/Tk license](https://www.tcl-lang.org/software/tcltk/license.html) |
