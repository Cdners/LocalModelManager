# Local Model Manager

[简体中文](README.md) · [English](README.en.md)

A native Windows local AI runtime manager built with Python 3.12 and PySide6. Models are independent of inference runtimes, with manifest-based registration, a shared downloader, per-engine services, and configurable proxies.

## 0.3.0 architecture upgrade

llama.cpp, audio.cpp, and transcribe.cpp are implemented; five additional adapters are explicitly reserved. Import models through YAML/JSON manifests, Hugging Face repositories/URLs, GitHub Releases, HTTP(S), or local files/directories. Unknown GGUF files require an explicit runtime selection. Existing Qwen profiles remain compatible.

Configure Direct, System, HTTP, HTTPS, SOCKS5 or SOCKS5H under **Settings → Network**, with per-download overrides. See [architecture, capabilities and limits](docs/architecture.md) and the [importable manifest example](docs/examples/fun-asr-nano.yaml).

## Why this exists

A local GPU is useful for dictation, but installing a runtime, matching model files, managing launch arguments, and connecting OpenTypeless adds friction. Read the [scenario, problem, and solution](docs/why-local-model-manager.en.md).

Download the Windows x64 package from [Releases](https://github.com/Cdners/LocalModelManager/releases/latest).

## Interface and languages

Version 0.3.0 includes English and Simplified Chinese. Choose **Settings → General → Language**. The interface updates and saves the language immediately without restarting model services. Other settings are applied with **Save settings**.

Navigation, controls, service states, tables, profile dialogs, and the tray menu follow the selected language. Model IDs, paths, user input, transcripts, and original logs retain their contents.

The overview groups the active service, GPU usage, and application connection details. Settings are organized into General, Storage & services, Updates & access, and Network. GPU memory usage includes other applications.

## Requirements and installation

- Windows x64 with a compatible NVIDIA GPU and driver for the managed CUDA runtime.
- An application directory that your Windows account can write to.
- Network access to download runtimes and models; inference runs locally once installed.

Extract the complete release ZIP and open `LocalModelManager.exe`. Keep the `app/` directory beside it. The release package does not include models or runtime binaries.

Runtime, models, configuration, downloads, and logs are stored alongside the application by default. Move the whole portable directory to retain relative paths. Changing a configured storage directory does not move existing data.

## Run a model

Use **Overview → Install Qwen3 ASR** for the Qwen3-ASR-1.7B Q8_0 model and its matching MMProj, or import a local GGUF from **Model library**. The guided setup installs a CUDA runtime if needed and creates an ASR profile.

Model profiles contain the model files, listening address, port, GPU layers, and optional arguments. Start, stop, and restart managed services from the overview or tray. The manager verifies process identity before stopping a service.

## Connect OpenTypeless

Start an ASR profile and wait for **READY**. Open **Voice input** and copy the actual Base URL and Model ID into OpenTypeless's Local / Custom Whisper configuration. Leave the API key empty for the local service.

If Qwen returns a `language …<asr_text>` prefix, stop the service and enable **Compatibility Proxy** in **Edit profile → Advanced**. The connection panel will then use the proxy address. The proxy only removes the recognized prefix; it does not polish or rewrite the transcript.

Use the microphone or an audio file to test transcription. The page shows the original result, request duration, and real-time factor when the audio duration is available.

## Updates and background services

Runtime updates are downloaded and validated before replacing the existing engine. Managed services are restarted and health-checked; failures restore the previous runtime. Model downloads are pinned to repository revisions and support resumable transfers.

Application updates support a Generic JSON manifest or GitHub Releases. For this project, choose GitHub Releases in Settings and enter `Cdners/LocalModelManager`. Packages require SHA-256 validation. Application updates replace only the executable, dependencies, and application manifest; persistent data remains in place. No public update source is configured by default.

Closing or minimizing the window can send it to the tray. Exiting while services are active offers a choice to keep or stop them. Windows sign-in startup and automatic profile startup are separate settings and are disabled by default.

## Development

Use the project's Python 3.12 virtual environment, never a global interpreter:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r pyproject.toml --extra build
.\.venv\Scripts\python.exe main.py
```

Dependencies: PySide6, httpx[socks], PyYAML, nvidia-ml-py, packaging, psutil, and truststore. Build dependencies: PyInstaller and pytest. Audio conversion currently uses Python 3.12's `audioop`; Python 3.13 is not supported yet.

```powershell
.\build.ps1
```

The build runs tests, creates a one-folder application, and writes a ZIP plus SHA-256 file to `dist/`. Stop managed services and exit the packaged app before overwriting its files, or build separately with `-OutputRoot artifacts\release\LocalModelManager`.

English source strings and Chinese translations live in `lmm/i18n.py`. Bind translatable UI copy with `bind()` and format dynamic text with `tr()`. Keep model identifiers, persisted enum values, and user data independent of display language. `tests/test_i18n.py` checks placeholder parity, live switching, and data preservation.

`tools/preview_ui.py` renders both languages at two window sizes in an isolated preview workspace. It reads local service status without starting or changing model services. Generated previews and local acceptance records belong in `artifacts/`, which is excluded from source control.

## Third-party components

See [THIRD_PARTY.md](THIRD_PARTY.md). This independent project is not affiliated with OpenTypeless, Qwen, llama.cpp, or their maintainers.
