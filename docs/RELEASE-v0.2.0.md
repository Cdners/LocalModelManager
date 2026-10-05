# Local Model Manager v0.2.0

Windows 原生本地模型服务管理器，支持简体中文和英文。

面向这样的场景：电脑已经有 NVIDIA 显卡，希望使用 Qwen3-ASR 为 OpenTypeless 提供本地语音识别，却需要反复处理运行环境、模型文件、命令行参数和接口配置。

## 本次发布

- Qwen3-ASR Q8_0 与 CUDA 运行环境的引导安装。
- 模型下载、校验、断点续传及多服务配置。
- 服务启动、停止、重启、就绪检查与系统托盘。
- GPU 状态、实际 API 地址与 Model ID 复制。
- 真实麦克风/音频文件转写测试，以及可选 Qwen 前缀兼容代理。
- 中文、英文即时切换；优化概览、设置、模型与下载页面。
- 修复已有实例不可达时双击无响应的问题。

## 安装

下载 `LocalModelManager-0.2.0-windows-x64.zip`，完整解压后打开 `LocalModelManager.exe`，保留旁边的 `app/`。包内不含模型与 llama.cpp，首次安装需要联网。目标平台为 Windows x64、NVIDIA CUDA。

SHA-256 见同名 `.zip.sha256` 附件。第三方声明与许可证位于 `app/licenses/`。

## 验证与边界

35 项自动测试通过。开发环境已验证 RTX 5060 8GB、Qwen3-ASR-1.7B Q8_0、真实麦克风和 OpenTypeless 本地输入。硬件验证来自单台电脑，其他驱动/显卡组合需自行验收。界面中的 GPU 占用包含其他应用。此版本未进行代码签名。

这是独立的模型服务管理器，不包含聊天界面；OpenTypeless 的润色/翻译是否访问云端取决于其自身配置。

---

Native Windows manager for local llama.cpp services, with English and Simplified Chinese UI. This release includes guided Qwen3-ASR/CUDA setup, resumable model downloads, service lifecycle and tray controls, GPU monitoring, real microphone tests, copyable connection details, and an optional Qwen prefix compatibility proxy.

Extract the entire Windows x64 ZIP and keep `app/` beside the executable. Models and llama.cpp are downloaded separately. SHA-256 is provided as a separate asset; third-party notices are in `app/licenses/`. The executable is unsigned.

Validation: 35 automated tests passed, plus single-machine RTX 5060 8GB testing with Qwen3-ASR Q8_0, a real microphone, and OpenTypeless local text insertion. Compatibility with other hardware/driver combinations is not guaranteed.
