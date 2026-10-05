# Third-party components / 第三方组件

Local Model Manager uses the following upstream projects. Their licenses remain independent of this application's license.

本软件使用以下第三方项目，各自许可证独立适用。Windows 包的 `app/licenses/` 保留构建环境中的许可证与版本清单；`app/` 中的动态库可独立替换，替换版本需保持二进制兼容。

| Component | Upstream source |
| --- | --- |
| Python 3.12 | https://github.com/python/cpython/tree/3.12 |
| PySide6 / Shiboken6 | https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| Qt 6 | https://code.qt.io/cgit/qt/ |
| httpx / httpcore | https://github.com/encode/httpx · https://github.com/encode/httpcore |
| huggingface_hub | https://github.com/huggingface/huggingface_hub |
| nvidia-ml-py | https://pypi.org/project/nvidia-ml-py/ |
| psutil | https://github.com/giampaolo/psutil |
| packaging | https://github.com/pypa/packaging |
| truststore | https://github.com/sethmlarson/truststore |
| PyInstaller | https://github.com/pyinstaller/pyinstaller |

PySide6/Shiboken and the applicable Qt libraries are distributed under their open-source license options, including LGPLv3. No restriction on modification or reverse engineering for debugging modifications to these libraries is intended. Corresponding sources are available from the upstream repositories and [Qt source archives](https://download.qt.io/official_releases/qt/); use the versions in the packaged inventory. License texts are in `app/licenses/` and [docs/licenses/](docs/licenses/).

The application downloads **llama.cpp** and model files separately. They are not included in the application ZIP. Check each selected runtime/model's own license and model card:

- llama.cpp: https://github.com/ggml-org/llama.cpp
- Qwen3-ASR GGUF: https://huggingface.co/ggml-org/Qwen3-ASR-1.7B-GGUF
- Qwen3-ASR: https://github.com/QwenLM/Qwen3-ASR

OpenTypeless is a separate application. Its code and binaries are not included in this repository or release.
