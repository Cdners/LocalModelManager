# Local Model Manager

[简体中文](README.md) · [English](README.en.md)

Windows 原生本地 AI Runtime 管理器，Python 3.12 + PySide6。模型与推理引擎独立管理：支持多 Runtime、Manifest 模型目录、统一下载和代理；不包含聊天界面。

## 0.3.0 架构升级

已实现 llama.cpp、audio.cpp、transcribe.cpp，另预留 5 种 Adapter。新增模型通过 YAML / JSON Manifest 声明来源、文件与 Runtime，不按 GGUF 后缀猜测引擎。

在「模型库」选择目录条目或导入 HF / GitHub Release / HTTP(S) / 本地文件和目录；「运行环境」按引擎分别安装和更新；「设置 → 网络」配置全局代理，下载任务可单独覆盖。旧版 Qwen3-ASR Profile 保持兼容。

完整接口、已实现与预留范围、代理行为和限制见 **[架构与使用说明](docs/architecture.md)**；可导入 **[Manifest 示例](docs/examples/fun-asr-nano.yaml)**。

## 为什么做这个工具

已有 NVIDIA 显卡，想让 OpenTypeless 使用本地语音识别，却被运行环境、模型配套文件、启动参数和接口配置卡住？Local Model Manager 把这些步骤收进一个 Windows 桌面界面。

从真实使用场景出发，阅读 **[遇到的问题与解决方案](docs/why-local-model-manager.md)**。

## 下载与快速开始

1. 在 [Releases](https://github.com/Cdners/LocalModelManager/releases/latest) 下载 Windows x64 ZIP 并完整解压。
2. 打开 `LocalModelManager.exe`，在「概览」安装 Qwen3 ASR。
3. 启动模型并等待就绪，在「语音输入」测试麦克风。
4. 复制页面上的 Base URL 和实际 Model ID，填入 OpenTypeless 的本地识别配置。

支持简体中文 / English，目标平台为 Windows x64 + NVIDIA CUDA。发布包不包含模型，首次安装需要联网。

## 界面与语言

0.3.0 保留的简体中文和英文界面。在「设置 → 常规 → 显示语言」切换，立即生效并保存；其他设置仍需点击保存。导航、按钮、状态、表格、设置、模型配置弹窗和托盘菜单随语言切换，模型服务无需重启。模型 ID、路径、输入内容、识别结果与原始日志保留原文。

概览将服务状态与显卡信息并排展示，连接配置可直接复制。设置分为常规、存储与服务、更新与访问、网络；下载页面提供空状态和入口。显存数字是所有应用的总占用。

开发者在 `lmm/i18n.py` 维护英文原文与中文翻译，通过 `bind()` 绑定可即时翻译的控件文案，通过 `tr()` 格式化动态文案。内部状态和枚举保持稳定的英文值，翻译只发生在展示层。`tests/test_i18n.py` 检查占位符、切换后的状态保持和用户数据不被改写。

界面回归使用 `tools/preview_ui.py` 生成隔离工作空间中的两种语言、7 个页面、两种窗口尺寸的预览，不启动或修改模型服务。截图与报告保存在 `artifacts/ui-<版本>/`，该目录不进入源码发布。

## 开发环境

使用项目自己的 `.venv`，不要安装依赖到全局 Python。需要 Windows x64、NVIDIA 驱动；本机开发验证目标为 RTX 5060 8GB。

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r pyproject.toml --extra build
.\.venv\Scripts\python.exe main.py
```

依赖为 PySide6、httpx[socks]、PyYAML、nvidia-ml-py、packaging、psutil、truststore；开发额外使用 PyInstaller 和 pytest。音频转换使用 Python 3.12 标准库 audioop，升级至 Python 3.13 前需替换该模块。

## 安装

将发布 ZIP 完整解压到有写入权限的目录，运行 `LocalModelManager.exe`。不要只复制 EXE：`app/` 也必须保留。首次启动先显示界面，再异步检查；没有运行环境时在「运行环境」点击「下载 / 更新」，或在「概览」点击「安装 Qwen3 ASR」。

模型、runtime、日志目录默认相对程序目录，可在「设置」调整。移动整个便携目录后，相对路径继续有效。指定外部绝对路径的文件不会自动搬迁。目录变更前停止服务和下载；已有数据不会自动移动。

## 构建

```powershell
.\build.ps1
```

先运行测试，再构建 one-folder：`dist/LocalModelManager/LocalModelManager.exe`，依赖在 `app/`。构建仅替换应用文件，保留 dist 内模型、runtime、配置、下载和日志。正在运行的 EXE/监督器可能锁定应用文件，重新构建前应从托盘停止模型并退出管理器。

发布 ZIP 仅包含 EXE、app 和 app_manifest.json，不打包模型或 runtime。ZIP 附带 SHA-256 文件。

## 运行环境管理

通过官方 `ggml-org/llama.cpp` GitHub latest stable release 获取 Windows x64 CUDA 包，动态选择资产及匹配的 cudart 依赖。如 stable release 只指向对应构建，跟随该官方构建，不选择任意 nightly。读取 NVIDIA 驱动能力，下载后验证 SHA-256（资产提供时）、大小、`--version` 和 CUDA 设备。

同一 CUDA 主版本的较新 minor 包可能依赖驱动的 minor compatibility；最终以实际启动和 API 验证为准。无法验证时保留旧 runtime，不安装 CPU-only 版本，也不改动系统驱动。

更新先下载、解压、验证，再停止使用该 Runtime 的已管理服务，备份旧 runtime、替换、恢复服务并检查 API；失败恢复旧版。runtime 崩溃中断事务会在下次启动恢复。备份保留在 runtime 相邻目录，供人工检查，程序不批量清理历史数据。

自动检查默认每天一次，自动下载和安装默认关闭，可分别启用。

## 模型下载

模型库提供 Manifest 目录，支持输入 Hugging Face repo/URL、GitHub Release、HTTP(S) URL，或选择本地文件/目录。选择主 GGUF 时自动勾选唯一匹配的 mmproj；歧义或缺失时提示人工核对。LLM 可关闭“需要 MMProj”。无法确定 Runtime 时必须人工选择，不按后缀默认 llama.cpp。

下载固定仓库 commit，支持暂停、取消、重试和 HTTP Range 断点续传，显示进度、速度、大小和 ETA。重启后未完成任务显示 Paused，手动继续。`.part` 只有完成大小/hash 校验才改名；每个模型有独立 metadata 和安装索引。HF token 可选，使用当前 Windows 用户 DPAPI 加密，绝不放进任务描述和日志。

模型更新每天检查 hash/etag/大小；远端只新增无关提交不会触发重下。默认不自动下载。开启自动更新或手动更新后，下载到新 commit 目录，通过验证才切换 Profile；旧模型不覆盖。

## Qwen3-ASR 示例

点击 Dashboard 的“安装 Qwen3 ASR（Q8 + CUDA）”，自动安装 runtime、下载官方 Q8_0 和 mmproj，创建 `qwen3-asr-17b-q8`，启动 `127.0.0.1:8000`。单独从 Models 下载则会先询问是否创建 Profile。

普通流程：Models → Download Q8_0 → Create Profile → Start → READY。默认 full GPU offload、parallel 1、上下文 4096（可在 Advanced 覆盖）。启动参数按当前 runtime `--help` 生成，不使用 Router。端口冲突时停止本次操作，不修改其他服务。

每个服务由独立监督器捕获输出、轮转日志，管理器退出后可继续运行。Stop 前核对 PID、创建时间、程序路径和完整命令行；只有自己的确认身份的进程才会收到停止信号。

## OpenTypeless 配置

OpenTypeless 页选中 READY 的 ASR Profile 后生成：

* Provider：Local / Custom Whisper（实际选项名称取决于 OpenTypeless 版本）
* Base URL：`http://127.0.0.1:8000/v1`
* Model：从当前 `/v1/models` 实际读取，使用 Copy Model ID
* API Key：本地服务不要求密钥，留空；若第三方客户端强制非空，可填任意占位值

Test Microphone 开始录音，Stop 保存单声道 16kHz PCM WAV 并发送 multipart `/v1/audio/transcriptions`。结果显示原始响应、文字、录音时长、请求总耗时和 RTF。几乎静音时不发送请求，避免把静音幻觉当成识别结果。文件保存到 `downloads/recordings`，最后一次结果在 `config/last_asr_result.json`。

如果实际响应带 `language Chinese<asr_text>`，停止 Profile，在 Advanced 开启 Compatibility Proxy 再启动。代理默认关闭，开启后监听 127.0.0.1:8001，保持原音频 multipart，只去掉该固定格式的文本前缀；转发 `/v1/models` 与 `/health`。延迟取决于本机，不能保证固定几毫秒。

## 自启动与托盘

Settings 可启用 Windows 登录启动、启动进入托盘、自动启动已勾选 Profile。注册表只使用当前用户 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\LocalModelManager`；关闭仅删除这一项。移动程序后下次启动会修正已启用的路径，不需要管理员权限。

关闭窗口、最小化默认进入托盘；双击图标恢复。托盘可操作每个 Profile、查看 GPU、启动自动 Profile、停止所有已管理模型。退出时存在运行服务会询问保留服务 / 停止并退出 / 取消，默认取消。

## 应用更新

软件更新支持 Generic JSON Manifest 或 GitHub Releases；未配置显示 `App update source not configured`。设置保存后检查、下载、安装并重启。默认每日检查，不自动安装应用更新。

Generic manifest 示例（替换为真实 HTTPS 包地址及 SHA-256）：

```json
{"version":"1.0.1","url":"https://example.com/LocalModelManager-1.0.1-windows-x64.zip","sha256":"<64 hex characters>","notes":"Release notes"}
```

本项目更新可选择 GitHub provider，填 `Cdners/LocalModelManager`。其他源填 `owner/repo`，latest stable release 应有唯一名称包含 LocalModelManager 的 Windows x64 ZIP，使用 GitHub 资产 SHA-256 digest。发布包需携带本项目 build 生成的 `app_manifest.json`。

下载后检查 hash 和包内版本，在 `updates/` staging。安装复制一份独立 helper（只复制应用本身），停止已管理服务，主进程退出后仅替换 EXE、app、app_manifest.json，重启后等待启动确认；失败回滚旧应用。模型、配置、runtime、日志、下载目录从不参与应用替换。保留 updates 的事务记录和备份。

## 常见问题

* **端口占用**：修改 Profile 端口或自行检查其他应用；管理器不会终止其他服务。
* **不是 READY**：查看 Profile 日志。进程存活不等于模型已加载；READY 要求 `/health`、`/v1/models`，ASR 还验证 transcription 路由。
* **GPU 显存不足**：Dashboard 显示整张显卡使用量，包含其他软件。自行释放显存或降低 offload/上下文；本软件不停止其他 AI 服务。
* **麦克风静音**：检查系统输入设备和“允许桌面应用访问麦克风”，在 OpenTypeless 页选择正确设备。
* **网络失败 / HF gated repo**：检查代理/网络/token，Downloads 重试可继续已下载部分。读取超时有上限；请求进行中的取消在网络读取返回后生效。
* **日志**：App 与各 Profile 分开保存，每个 20MiB × 5 backups；Clear View 只清界面。All 汇总显示，有界读取避免加载整份日志。
* **更新失败**：先读 Logs 及 config/updates 的 transaction 文件。备份不会自动删除。不要在服务运行时手工覆盖 runtime/DLL。
* **配置损坏**：程序保留原文件并报错，不静默重置。恢复可用 JSON 或备份后再启动。
* **LAN 访问**：默认仅 127.0.0.1。手动绑定其他地址会提示，不自动修改防火墙、UPnP 或端口映射。

## 项目目录

```
LocalModelManager.exe   应用入口
app/                   PyInstaller 依赖，仅应用更新会替换
config/                设置、Profiles、安装索引、下载状态、进程身份与事务回执
runtime/<adapter>/     按引擎隔离的 runtime 和 DLL
models/                按来源和 revision 隔离的模型文件
downloads/             ZIP 缓存、临时下载和录音
updates/               app staging、helper、备份与更新事务
logs/                  轮转日志
```

源码 `lmm/` 按配置、下载、runtime、模型、进程、API、音频、GPU、托盘、更新和 UI 划分。`tests/` 覆盖关键安全边界和 mock 网络行为。

命令行可选 `--minimized`、`--root <便携目录>`；`--setup-qwen` 触发同一个 GUI 安装流程，`--record-seconds 10` 在 READY 时录音 10 秒，`--test-audio <文件>` 触发 GUI 音频测试。已有实例时通过当前用户的本地 IPC 转发操作。


## 第三方组件

见 [THIRD_PARTY.md](THIRD_PARTY.md)。本项目与 OpenTypeless、Qwen、llama.cpp 及其维护方无隶属关系。
