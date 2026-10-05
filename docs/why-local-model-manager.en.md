# From a local GPU to everyday voice input

[Home](../README.en.md) · [简体中文](why-local-model-manager.md)

## The scenario

You already have an NVIDIA GPU and want to dictate into an editor, a chat app, or a document through OpenTypeless. You want speech recognition to run on your own Windows machine and to know which model and endpoint process the audio.

This project grew out of a real **Windows + RTX 5060 8GB + Qwen3-ASR + OpenTypeless** setup.

## The problem

Downloading a model is only one step. You still need a compatible CUDA runtime, the main GGUF and matching MMProj, launch arguments, a free port, and a working transcription endpoint. A running process may still be loading. The input app needs the actual model ID and URL. Some Qwen responses include a format prefix that should not appear in inserted text.

Repeating those steps in terminals, and keeping them working across updates, makes a useful local model awkward to use every day.

## The solution

Local Model Manager brings runtime installation, model downloads, saved service profiles, start/stop controls, health checks, microphone testing, and connection details into a native desktop application.

- **OpenTypeless** handles voice-input shortcuts and insertion into other applications.
- **Qwen3-ASR running through llama.cpp** transcribes the audio on the local GPU.
- **Local Model Manager** installs, configures, starts, checks, and updates the local service.
- An optional **local compatibility proxy** removes the recognized Qwen prefix. It does not polish text or call a cloud model.

The interface supports English and Simplified Chinese. Application updates, runtime updates, and model downloads have separate storage and validation paths.

## Walkthrough

1. Download the Windows x64 ZIP from [Releases](https://github.com/Cdners/LocalModelManager/releases/latest), extract the whole package, and run `LocalModelManager.exe`.
2. Use the overview's Qwen3 ASR setup action to install the CUDA runtime, Q8_0 model, and MMProj.
3. Start the profile and wait for READY. GPU memory figures include other applications.
4. Test a real microphone from the voice-input page.
5. Copy the displayed Base URL and actual Model ID into OpenTypeless's Local / Custom Whisper configuration. The local endpoint does not require an API key.
6. If the transcript contains `language …<asr_text>`, stop the profile, enable Compatibility Proxy in its advanced settings, restart, and copy the updated URL.
7. Test dictation and insertion in an application you use every day.

After downloading the model, ASR inference runs locally. Whether OpenTypeless's separate polishing or translation features contact cloud services depends on its own settings; this manager does not change those settings.

## Verification and scope

Development validation used an RTX 5060 8GB, Qwen3-ASR-1.7B Q8_0, real microphone audio, and OpenTypeless local transcription and text insertion. Version 0.2.0 passed 35 automated tests, with additional Windows checks for language switching and window restoration.

This is evidence from one machine, not a guarantee for every GPU, driver, or model. An 8GB GPU still needs enough free VRAM. Initial downloads require GitHub and Hugging Face access. The application targets Windows x64 and NVIDIA CUDA, does not bundle models, and does not provide a chat interface or replace the full OpenTypeless application.

This is an independent project, not affiliated with OpenTypeless, Qwen, llama.cpp, or their maintainers.
