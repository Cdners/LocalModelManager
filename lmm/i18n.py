"""English source strings and Simplified Chinese UI translations.

Only explicitly bound UI text is translated. Model IDs, paths, logs, transcripts,
and persisted state codes stay unchanged. Add new UI copy to ZH and bind it.
"""
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QMessageBox as QtMessageBox


ZH = {
    "Passed": "通过", "Pending": "等待", "Total GPU usage across all apps.": "显存占用包含其他应用。",
    "Remote file removed": "远程文件已移除", "Verifying SHA-256": "正在校验 SHA-256",
    "Checking runtime version and CUDA device": "正在检查运行环境版本与 CUDA 设备",
    "Choose a model or runtime to start your first download.": "在模型库或运行环境中，选择需要下载的内容。",
    "General": "常规", "Storage & services": "存储与服务", "Updates & access": "更新与访问",
    "Missing / incomplete": "缺失 / 不完整", "The main model is downloaded, but MMProj is incomplete.": "主模型已下载，但 MMProj 尚未完成。",
    "Overview": "概览", "Model library": "模型库", "Downloads": "下载任务",
    "Runtime": "运行环境", "Voice input": "语音输入", "Logs": "日志", "Settings": "设置",
    "LOCAL WORKSPACE": "本地工作空间", "Local model services": "本地模型服务",
    "Your models. On your machine.": "模型在本机，服务由你掌控。",
    "Manage services, monitor your GPU, and connect your apps.": "管理模型服务、查看显卡状态，并连接你的应用。",
    "Find, download, and manage GGUF models.": "查找、下载与管理 GGUF 模型。",
    "Track transfers and resume unfinished downloads.": "查看下载进度，继续未完成的任务。",
    "Manage the llama.cpp engine used by your services.": "管理模型服务使用的 llama.cpp 推理引擎。",
    "Connect OpenTypeless and test local speech recognition.": "连接 OpenTypeless，测试本地语音识别。",
    "Inspect application and model service output.": "查看管理器与模型服务的运行记录。",
    "Make this workspace your own.": "调整语言、启动行为与模型服务偏好。",
    "Active service": "当前模型服务", "Graphics card": "显卡状态", "App connection": "应用连接",
    "Service configuration": "服务配置", "Memory usage": "显存占用", "Quick actions": "快捷操作",
    "Start": "启动", "Stop": "停止", "Restart": "重启", "New": "新建", "Edit": "编辑",
    "Clone": "复制", "Delete": "删除", "Start service": "启动服务", "Stop service": "停止服务",
    "Restart service": "重启服务", "New profile": "新建配置", "Edit profile": "编辑配置",
    "Copy profile": "复制配置", "Delete profile": "删除配置",
    "STOPPED": "已停止", "READY": "已就绪", "RUNNING": "运行中", "STARTING": "启动中",
    "STOPPING": "停止中", "LOADING MODEL": "正在加载模型", "ERROR": "发生错误",
    "IDENTITY MISMATCH": "进程身份不匹配", "UNKNOWN": "未知",
    "Queued": "等待中", "Running": "进行中", "Pausing": "正在暂停", "Paused": "已暂停",
    "Cancelled": "已取消", "Failed": "失败", "Completed": "已完成",
    "Port {port}  ·  PID {pid}  ·  {kind}": "端口 {port}  ·  进程 {pid}  ·  {kind}",
    "Create a profile to start your first model service.": "创建模型配置，开始运行你的第一个本地服务。",
    "Health {health}     Model list {models}     Transcription {transcription}": "健康检查 {health}     模型列表 {models}     语音转写 {transcription}",
    "Base URL": "接口地址", "Model ID": "模型 ID", "Waiting for the service": "等待服务启动",
    "Copy Base URL": "复制接口地址", "Copy Model ID": "复制模型 ID", "Copy configuration": "复制连接配置",
    "Copied to clipboard": "已复制到剪贴板",
    "Install Qwen3 ASR": "安装 Qwen3 ASR", "Test microphone": "测试麦克风",
    "A quick setup for local speech recognition.": "一键准备本地语音识别所需的模型和环境。",
    "GPU · Reading…": "正在读取显卡…", "GPU unavailable": "暂时无法读取显卡",
    "Unavailable": "不可用", "VRAM": "显存",
    "{used} / {total}": "{used} / {total}",
    "Load  {load}%    ·    {temperature} °C\nPower  {power} W": "负载  {load}%    ·    {temperature} °C\n功耗  {power} W",
    "Recommended for speech": "语音识别推荐", "Q8_0 · Recommended for 8 GB GPUs\nModel 2.17 GB + MMProj 356 MB": "Q8_0 · 适合 8 GB 显存\n主模型 2.17 GB + MMProj 356 MB",
    "BF16 uses more memory: model 4.07 GB + MMProj 642 MB.": "BF16 需要更多显存：主模型 4.07 GB + MMProj 642 MB。",
    "Download Q8_0": "下载 Q8_0", "Download BF16": "下载 BF16",
    "Browse Hugging Face": "浏览 Hugging Face", "Repository or search keywords": "仓库名称或搜索关键词",
    "Load repository": "读取仓库", "Search Hugging Face": "搜索 Hugging Face",
    "Import local GGUF": "导入本地 GGUF", "Download selected": "下载所选文件",
    "Select": "选择", "GGUF file": "GGUF 文件", "Size": "大小", "Type": "类型",
    "Installed models": "已安装模型", "Model": "模型", "Revision": "版本", "Status": "状态",
    "Installed": "已安装", "Up to date": "已是最新", "Update available": "有可用更新",
    "File missing": "文件缺失", "Missing": "缺失", "Unavailable upstream": "上游不可用",
    "Check model updates": "检查模型更新", "Apply model updates": "下载并切换更新", "Open model folder": "打开模型目录",
    "Double-click a result to list its GGUF files.": "双击搜索结果，查看 GGUF 文件。",
    "No matching GGUF repositories found.": "未找到匹配的 GGUF 仓库。",
    "Revision {revision} · Matching MMProj files are selected automatically.": "版本 {revision} · 选择主模型时，会自动勾选匹配的 MMProj。",
    "No matching MMProj found. Check the model requirements; LLMs usually do not need one.": "未找到匹配的 MMProj，请核对模型说明；纯文本模型通常不需要。",
    "No models installed yet. Download a recommended model or import a local GGUF.": "尚未安装模型，可以下载推荐模型或导入本地 GGUF。",
    "Check complete · {count} files can be updated": "检查完成 · {count} 个文件可更新",
    "Resumable downloads. Unfinished tasks can be continued after restarting the app.": "支持断点续传，重启软件后可以继续未完成的下载。",
    "No downloads yet": "暂无下载任务", "Task / File": "任务 / 文件", "State": "状态",
    "Progress": "进度", "Downloaded": "已下载", "Speed": "速度", "ETA / Detail": "剩余时间 / 详情",
    "Pause": "暂停", "Resume / Retry": "继续 / 重试", "Cancel": "取消",
    "Check for updates": "检查更新", "Download / Update": "下载 / 更新", "Install downloaded version": "安装已下载版本",
    "Engine information": "引擎信息", "Runtime diagnostics": "运行环境详情",
    "The CUDA runtime is managed independently. Updates back up the engine, restart managed services, and roll back if health checks fail.": "独立管理 CUDA 运行环境。更新时备份引擎、重启已管理的服务，并在健康检查失败时回滚。",
    "Installed: {binary}   ({release})\nLatest: {latest}\nBackend: {backend}": "已安装：{binary}   （{release}）\n最新版本：{latest}\n计算后端：{backend}",
    "Not checked": "尚未检查", "CUDA not installed": "CUDA 尚未安装", "llama.cpp is not installed": "尚未安装 llama.cpp",
    "Status: {status}": "状态：{status}",
    "OpenTypeless connection": "OpenTypeless 连接配置",
    "Provider: Local / Custom Whisper\nBase URL: {url}\nModel: {model}\nAPI key: leave empty\n\nThe model ID is read from your running service.": "服务提供方：Local / Custom Whisper\n接口地址：{url}\n模型 ID：{model}\nAPI 密钥：留空\n\n模型 ID 来自当前运行的服务。",
    "Select an ASR profile and start the service to see its connection settings.": "选择语音识别配置并启动服务，即可查看连接设置。",
    "Speech test": "语音识别测试", "Stop and transcribe": "停止并转写", "Choose audio file": "选择音频文件",
    "Refresh microphones": "刷新麦克风", "Windows default microphone": "Windows 默认麦克风",
    "Audio is saved as mono 16 kHz PCM WAV.": "录音保存为单声道 16 kHz PCM WAV。",
    "Your transcript will appear here…": "识别文字将显示在这里…", "Raw response": "原始响应",
    "● Recording…  {seconds:05.1f}s  ·  Maximum 5 minutes": "● 正在录音…  {seconds:05.1f} 秒  ·  最长 5 分钟",
    "Saving and transcribing…": "正在保存并转写…",
    "Recording is almost silent. Check your Windows input device and microphone permissions.": "录音几乎静音，未发送识别。请检查 Windows 输入设备和麦克风权限。",
    "Audio: {duration:.2f}s  ·  Request: {milliseconds:.0f} ms  ·  RTF: {rtf:.3f}": "音频：{duration:.2f} 秒  ·  请求耗时：{milliseconds:.0f} 毫秒  ·  实时率：{rtf:.3f}",
    "Request: {milliseconds:.0f} ms": "请求耗时：{milliseconds:.0f} 毫秒",
    "Transcribed · WAV saved in downloads/recordings": "转写完成 · WAV 已保存到 downloads/recordings",
    "Qwen prefix detected. Stop the service and enable Compatibility Proxy in Edit profile → Advanced, then restart.": "检测到 Qwen 前缀。停止服务后，在「编辑配置 → 高级选项」中开启兼容代理，再重新启动。",
    "Test audio": "测试音频", "Audio (*.wav *.mp3 *.flac *.m4a *.ogg)": "音频 (*.wav *.mp3 *.flac *.m4a *.ogg)",
    "All services": "全部服务", "Application": "管理器", "Pause / Resume": "暂停 / 继续",
    "Clear view": "清空显示", "Copy": "复制", "Open log folder": "打开日志目录",
    "Log display paused": "日志显示已暂停", "Log display resumed": "日志显示已恢复",
    "Appearance & language": "外观与语言", "Language": "显示语言",
    "Changes to language take effect immediately.": "切换语言后立即生效，其他设置在保存后生效。",
    "Startup & window": "启动与窗口", "Run at Windows sign-in": "Windows 登录时启动",
    "Start in the system tray": "启动时进入托盘", "Start enabled model profiles": "自动启动已勾选的模型配置",
    "Minimize to tray": "最小化时进入托盘", "Close to tray": "关闭窗口时进入托盘",
    "Storage": "文件存储", "Models folder": "模型目录", "Runtime folder": "运行环境目录", "Logs folder": "日志目录",
    "Service defaults": "服务默认值", "Host": "监听地址", "Port": "端口", "GPU layers": "GPU 加载层数",
    "Automatic updates": "自动更新", "Check runtime daily": "每天检查运行环境更新",
    "Download runtime updates": "自动下载运行环境更新", "Install runtime updates (restart & rollback)": "自动安装运行环境更新（含重启与回滚）",
    "Check models daily": "每天检查模型更新", "Download and switch model updates": "自动下载并切换模型更新",
    "Software updates": "软件更新", "Update provider": "更新源类型", "Manifest URL / GitHub repository": "更新地址 / GitHub 仓库",
    "JSON manifest": "JSON 更新清单", "GitHub Releases": "GitHub Releases", "Check app updates daily": "每天检查软件更新",
    "Hugging Face access": "Hugging Face 访问", "Access token (optional)": "访问令牌（可选）",
    "Leave empty to keep the saved token. Encrypted with Windows DPAPI.": "留空保留已存令牌，使用 Windows DPAPI 加密保存。",
    "Remove saved token": "删除已保存的令牌", "Save settings": "保存设置", "Settings saved": "设置已保存",
    "Download app update": "下载软件更新", "Install and restart": "安装并重启",
    "App update source not configured": "尚未配置软件更新源",
    "Installed {current} · Latest {latest}": "已安装 {current} · 最新 {latest}",
    "Update verified and ready to install.": "更新已下载并校验，可以安装并重启。",
    "Ready · Your workspace is stored beside the application": "就绪 · 工作空间保存在程序目录",
    "Model profile": "模型配置", "Profile ID": "配置 ID", "Name": "名称", "Main model GGUF": "主模型 GGUF",
    "Browse": "浏览", "Requires MMProj": "需要 MMProj", "Allow this profile to start automatically": "允许自动启动此配置",
    "Advanced": "高级选项", "Parallel requests": "并发请求数", "Compatibility proxy port": "兼容代理端口",
    "Only remove the Qwen language …<asr_text> prefix": "仅去除 Qwen language …<asr_text> 前缀",
    "Compatibility Proxy": "兼容代理", "Extra arguments (JSON array)": "附加参数（JSON 数组）",
    "Speech recognition (ASR)": "语音识别（ASR）", "Text generation (LLM)": "文本生成（LLM）", "Vision": "视觉模型",
    "Select GGUF": "选择 GGUF", "Save": "保存", "OK": "确定", "Yes": "是", "No": "否", "Close": "关闭",
    "Open Local Model Manager": "打开 Local Model Manager", "Start all auto-start profiles": "启动所有自动启动配置",
    "Stop all managed models": "停止所有已管理模型", "Exit": "退出", "Exit Local Model Manager": "退出 Local Model Manager",
    "Local Model Manager is still running in the background.": "Local Model Manager 仍在后台运行。",
    "Managed model services are still running.": "仍有模型服务在运行。",
    "Keep services and exit": "保留服务并退出管理器", "Stop services and exit": "停止服务并退出",
    "Network access": "网络访问",
    "This address may allow other devices to access the model API. Continue?": "此地址可能允许其他设备访问模型 API。是否继续？",
    "A non-loopback host exposes the API to other devices. The app will not configure your firewall. Continue?": "非回环地址会将模型 API 暴露给其他设备。程序不会配置防火墙。是否继续？",
    "Delete the configuration for {name}? Model files will be kept.": "删除 {name} 的配置？模型文件会保留。",
    "Stop the service and wait for updates to finish before editing or deleting its profile.": "请先停止服务并等待更新完成，再编辑或删除配置。",
    "Create a profile first.": "请先创建模型配置。", "An update is in progress. Please wait.": "更新正在进行，请等待完成。",
    "An operation is already running for this profile.": "此配置的操作正在进行。",
    "No model ID has been returned by /v1/models yet.": "尚未从 /v1/models 获取模型 ID。",
    "Select at least one GGUF file.": "请至少选择一个 GGUF 文件。",
    "The official repository did not return a matching MMProj.": "官方仓库未返回匹配的 MMProj。",
    "Create a profile from the downloaded model?": "是否使用已下载的模型创建配置？",
    "Create profile": "创建配置", "No confirmed model updates. Check for updates first.": "没有已确认的模型更新，请先检查。",
    "A runtime operation is in progress.": "运行环境操作正在进行。",
    "No verified runtime is ready to install.": "没有已验证的待安装运行环境。",
    "Qwen3 ASR is ready for a microphone test": "Qwen3 ASR 已就绪，可以测试麦克风",
    "Wait for the ASR service to be ready.": "请等待语音识别服务就绪。",
    "Start the ASR service and wait until it is ready.": "请先启动语音识别服务并等待就绪。",
    "Select an ASR profile.": "请选择语音识别配置。",
    "Folders and host cannot be empty.": "目录和监听地址不能为空。",
    "Default port must be at least 1.": "默认端口不能小于 1。",
    "Stop model services and downloads before changing folders.": "请先停止模型服务和下载，再更改目录。",
    "Configure an update source and check for a new version first.": "请先配置更新源并检查可用的新版本。",
    "Download and verify the app update first.": "请先下载并验证软件更新。",
    "Wait for other background tasks before installing the app update.": "请等待其他后台任务结束，再安装软件更新。",
    "Install app update": "安装软件更新",
    "The app will restart. Managed models will stop and restart after the update. Continue?": "软件将重启。已管理的模型会先停止，并在更新后重新启动。是否继续？",
    "Extra args must be an array.": "附加参数必须是 JSON 数组。", "Profile ID already exists.": "配置 ID 已存在。",
    "Recovering services": "恢复服务状态", "Stopping managed services": "停止已管理的服务",
    "Download models": "下载模型", "Read Qwen3 ASR repository": "读取 Qwen3 ASR 仓库",
    "Install downloaded runtime": "安装已下载的运行环境", "Microphone ASR test": "麦克风识别测试",
    "Audio ASR test": "音频识别测试", "Preparing app update": "准备软件更新", "Checking running services": "检查运行中的服务",
    "Profile ID must contain only letters, numbers, - and _.": "配置 ID 只能包含字母、数字、短横线和下划线。",
    "A name and a supported model type are required.": "请填写名称并选择支持的模型类型。",
    "Ports must be between 1 and 65535.": "端口必须在 1 到 65535 之间。",
    "Proxy and model service need different ports.": "代理和模型服务必须使用不同端口。",
    "Invalid parallel slots or GPU layers.": "并发数或 GPU 加载层数无效。",
    "Enter one host address.": "请输入单个监听地址。",
    "Use the dedicated model/host/port fields; router mode is not supported.": "请使用专用的模型、地址和端口字段；暂不支持路由模式。",
    "Extra arguments must be a JSON array of strings.": "附加参数必须是由字符串组成的 JSON 数组。",
    "The recording is too short or contains no microphone audio.": "录音太短或未收到麦克风音频。",
    "Please select a mono or stereo microphone.": "请选择单声道或双声道麦克风。",
    "A recording is already active.": "已有录音正在进行。",
    "No microphone found. Select an input device in Windows sound settings.": "未发现麦克风。请在 Windows 声音设置中选择输入设备。",
    "Not recording.": "当前没有正在进行的录音。",
    "Unsupported microphone PCM format.": "不支持此麦克风的 PCM 格式。",
    "/v1/models did not return an OpenAI model list.": "/v1/models 未返回 OpenAI 兼容的模型列表。",
    "The server has not exposed a model ID yet.": "服务尚未提供模型 ID。",
    "Transcription JSON is missing its text field.": "转写结果的 JSON 缺少 text 字段。",
    "The model ID must be read from a ready /v1/models endpoint first.": "请先从已就绪的 /v1/models 接口读取模型 ID。",
    "Transcription response is not JSON.": "转写响应不是 JSON。",
    "The managed server exited while loading. See its profile log.": "模型服务在加载时退出，请查看对应的服务日志。",
    "Hugging Face did not return an immutable commit revision.": "Hugging Face 未返回固定的提交版本。",
    "Unsafe repository filename.": "仓库文件名不安全。",
    "Selected file is not in the pinned repository listing.": "所选文件不在已固定版本的仓库列表中。",
    "Unsafe model path.": "模型路径不安全。", "Remote model size is missing.": "远程模型缺少文件大小信息。",
    "Unverified file already exists; choose another model directory.": "目录中已存在未经验证的文件，请选择其他模型目录。",
    "Downloaded file size verification failed.": "下载文件的大小校验失败。",
    "SHA-256 mismatch; invalid data removed, installed files preserved.": "SHA-256 校验失败；已清理无效数据，已安装文件保持不变。",
    "Not enough free disk space for this download.": "磁盘可用空间不足，无法下载。",
    "Remote file size differs from the pinned metadata.": "远程文件大小与固定版本的元数据不一致。",
    "Remote file size is unavailable; refusing an unbounded download.": "无法读取远程文件大小，已停止无限制下载。",
    "Not enough free disk space.": "磁盘可用空间不足。", "Incomplete response.": "响应内容不完整。",
    "Invalid resume Content-Range; partial file was not appended.": "断点续传的 Content-Range 无效，未追加到已有文件。",
    "Remote object changed; restarting download.": "远程文件已改变，正在重新下载。",
    "Download exceeded the declared size.": "下载内容超过声明的文件大小。",
    "A complete main GGUF file is required.": "需要完整的主模型 GGUF 文件。",
    "This model requires MMProj, but no compatible file was found.": "该模型需要 MMProj，但未找到兼容文件。",
    "MMProj file is missing or incomplete.": "MMProj 文件缺失或不完整。",
    "Server startup identity was not confirmed. Inspect process recovery before retrying.": "未能确认启动的服务身份，请检查进程恢复状态后重试。",
    "llama.cpp runtime is not installed.": "llama.cpp Runtime 尚未安装。",
    "Untrusted process stop receipt.": "停止进程的回执不可信。",
    "Could not stop the managed process.": "无法停止已管理的进程。",
    "Model supervisor is still stopping the server.": "模型监护进程仍在停止服务。",
    "Model supervisor exited; check the profile log.": "模型监护进程已退出，请查看服务日志。",
    "PID identity has changed; refusing to signal this process.": "进程 ID 的身份已改变，已阻止向该进程发送信号。",
    "This runtime installer requires Windows x64.": "此运行环境安装器需要 Windows x64。",
    "Windows runtime installation is only available on Windows.": "只能在 Windows 上安装此运行环境。",
    "NVIDIA GPU/driver not detected. CPU-only runtime will not be installed.": "未检测到 NVIDIA 显卡或驱动，不会安装纯 CPU 运行环境。",
    "NVIDIA CUDA driver could not initialize.": "无法初始化 NVIDIA CUDA 驱动。",
    "Release has no compatible Windows x64 CUDA package. CPU fallback is disabled.": "此版本没有兼容的 Windows x64 CUDA 安装包，已禁用 CPU 回退。",
    "Expected the latest stable llama.cpp release.": "需要最新的稳定版 llama.cpp。",
    "Insufficient disk space to extract archive.": "磁盘空间不足，无法解压。",
    "Runtime staging directory is outside the managed parent.": "运行环境暂存目录位于管理范围之外。",
    "Runtime stage has not been verified.": "运行环境暂存文件尚未验证。",
    "Runtime directory contains unmanaged files; choose an empty directory.": "运行环境目录包含非本程序管理的文件，请选择空目录。",
    "Runtime recovery paths do not match this installation.": "运行环境恢复路径与当前安装不匹配。",
    "Unsafe archive path.": "压缩包内路径不安全。", "Archive links are not allowed.": "不允许压缩包包含链接。",
    "Runtime package must contain one llama-server.exe.": "运行环境安装包必须包含一个 llama-server.exe。",
    "CUDA backend DLL is missing.": "缺少 CUDA 后端 DLL。",
    "Update manifest must be a JSON object.": "更新清单必须是 JSON 对象。",
    "Update packages must use HTTPS (HTTP allowed only on loopback for testing).": "更新包必须使用 HTTPS，只有本机测试允许 HTTP。",
    "Do not embed credentials in update URLs.": "请勿在更新地址中包含凭据。",
    "Update SHA-256 must contain 64 hex characters.": "更新的 SHA-256 必须包含 64 个十六进制字符。",
    "Update archive must contain one LocalModelManager.exe.": "更新包必须包含一个 LocalModelManager.exe。",
    "Package identity/version does not match its update manifest.": "安装包标识或版本与更新清单不匹配。",
    "App package is incomplete.": "软件安装包不完整。",
    "Install app updates from the packaged EXE. Source mode supports checking and downloading.": "请在打包后的 EXE 中安装软件更新；源码运行支持检查与下载。",
    "App update stage was not verified.": "软件更新暂存文件尚未验证。",
    "Update job location is invalid.": "更新任务位置无效。",
    "Update acknowledgement path is invalid.": "更新确认路径无效。",
    "Updater may only replace its parent application.": "更新器只能替换启动它的应用。",
    "Manager did not exit. No application files were changed.": "管理器尚未退出，未修改应用文件。",
    "Invalid app update acknowledgement.": "软件更新确认无效。",
    "Invalid update acknowledgement path.": "更新确认路径无效。",
    "Invalid update version.": "更新版本号无效。", "Unknown app update provider.": "未知的软件更新源。",
    "App update paths are outside the managed updates directory.": "软件更新路径位于管理的更新目录之外。",
    "The updated application did not acknowledge a healthy startup.": "更新后的应用未确认正常启动。",
    "A model supervisor is still exiting. Retry the app update shortly.": "模型监护进程仍在退出，请稍后重试软件更新。",
    "Use GitHub owner/repo.": "请输入 GitHub 的 owner/repo。",
    "The GitHub release must have exactly one LocalModelManager Windows x64 ZIP asset.": "GitHub 发布必须包含且仅包含一个 LocalModelManager Windows x64 ZIP 文件。",
    "Credential storage requires Windows DPAPI.": "凭据存储需要 Windows DPAPI。",
    "Cannot access the manager lock. Check write access to the config folder.": "无法访问管理器的运行锁，请检查 config 文件夹的写入权限。",
    "The running manager did not respond. Exit it from the system tray and try again.": "已联系到运行中的管理器，但窗口未响应。请从托盘退出管理器后重试。",
    "A manager is already running but its window cannot be reached. Exit the manager in the other Windows account or background test environment and try again.": "已有管理器实例，但无法唤出它的窗口。请退出其他 Windows 账户或后台测试环境中的管理器后重试。",
}



ZH.update({'Import models and choose a compatible runtime.': '导入模型并选择兼容的运行环境。', 'Manage independent inference engines.': '独立管理各种推理引擎。', 'Network': '网络', 'Download proxy': '下载代理', 'Proxy mode': '代理模式', 'Proxy URL': '代理地址', 'Proxy URL (optional)': '可直接粘贴标准代理 URL', 'Use global proxy': '使用全局代理', 'Direct': '直连（不使用代理）', 'System proxy': '使用系统代理', 'HTTP proxy': 'HTTP 代理', 'HTTPS proxy': 'HTTPS 代理', 'SOCKS5 (local DNS)': 'SOCKS5（本地 DNS）', 'SOCKS5H (proxy DNS)': 'SOCKS5H（代理解析 DNS）', 'Username (optional)': '用户名（可选）', 'Password (optional)': '密码（可选）', 'Leave empty to keep the saved password.': '留空保留已保存的密码。', 'Test connection': '测试连接', 'Test Hugging Face': '测试 Hugging Face', 'Test GitHub': '测试 GitHub', 'Applies to metadata, models, runtimes and app updates. Local inference stays direct.': '应用于元数据查询、模型、运行环境和软件更新；本地推理始终直连。', 'Model Registry': '模型目录', 'Download and configure': '下载并配置', 'Import manifest': '导入模型清单', 'Resolve source': '解析来源', 'Local file': '本地文件', 'Local directory': '本地目录', 'Model file': '模型文件', 'Model file / directory': '模型文件 / 目录', 'Runtime adapter': '运行环境适配器', 'Select runtime explicitly': '请选择运行环境', 'Reserved': '已预留，尚未实现', 'Embedding': '向量嵌入', 'Reranker': '重排序', 'Text to speech (TTS)': '语音合成（TTS）', 'Backend': '计算后端', 'Runtime options (JSON)': '运行环境选项（JSON）', 'Select model file': '选择模型文件', 'Compatible runtime': '兼容的运行环境', 'Recommended': '推荐', 'Inspect local model': '检查本地模型', 'Select at least one model file.': '请至少选择一个模型文件。', 'Pause the task before changing its proxy.': '请先暂停任务，再更改代理。', 'Not installed': '未安装', 'Proxy for new downloads': '新下载任务的代理', 'Custom proxy': '自定义代理', 'Slow download: pause to change proxy or retry.': '下载较慢：可暂停后更换代理或重试。', 'Runtime adapter · {runtime}': '运行环境 · {runtime}'})


ZH.update({"Task":"任务","Architecture":"架构","Format":"格式","Unknown":"未知","Model source / search keywords":"模型来源 / 搜索关键词","Double-click a result to list its model files.":"双击结果查看模型文件。","No matching model repositories found.":"未找到匹配的模型仓库。","No models installed yet. Import a model source or choose a catalog entry.":"暂无模型，请导入模型来源或选择模型目录中的条目。"})

ZH.update({
    'Not configured':'尚未配置',
    'Install and switch':'安装并切换',
    'Switch to this model':'切换到此模型',
    'Install this model and its runtime, then switch the active service.':'自动安装模型和运行环境，完成后切换服务。',
    'This runtime is planned, but not available yet.':'此运行环境尚未实现，暂不能检查或安装。请使用 llama.cpp、audio.cpp 或 transcribe.cpp。',
    'Install the selected runtime first.':'请先安装所选模型的运行环境。',
})

_language = "zh"
_english = {value: key for key, value in ZH.items()}


def set_language(language):
    global _language
    _language = language if language in {"zh", "en"} else "en"


def tr(source, **values):
    source = _english.get(str(source), str(source))
    if source not in ZH and not values and "\n" in source:
        return "\n".join(tr(line) for line in source.split("\n"))
    text = ZH.get(source, source) if _language == "zh" else source
    return text.format(**values) if values else text


def bind(widget, source, setter="setText", **values):
    bindings = getattr(widget, "_translations", {})
    bindings[setter] = (source, values)
    widget._translations = bindings
    getattr(widget, setter)(tr(source, **values))
    return widget


def retranslate(widget):
    for child in [widget, *widget.findChildren(QObject)]:
        for setter, (source, values) in getattr(child, "_translations", {}).items():
            getattr(child, setter)(tr(source, **values))
        headers = getattr(child, "_translated_headers", None)
        if headers:
            child.setHorizontalHeaderLabels([tr(text) for text in headers])


class MessageBox(QtMessageBox):
    @staticmethod
    def _show(icon, parent, title, text, buttons, default):
        box = MessageBox(parent)
        box.setIcon(icon); box.setWindowTitle(tr(title)); box.setTextFormat(Qt.TextFormat.PlainText); box.setText(tr(text))
        box.setStandardButtons(buttons)
        for name in ("Ok", "Yes", "No", "Cancel", "Save", "Close"):
            button = box.button(getattr(QtMessageBox.StandardButton, name))
            if button: button.setText(tr("OK" if name == "Ok" else name))
        if default != QtMessageBox.StandardButton.NoButton: box.setDefaultButton(default)
        return QtMessageBox.StandardButton(box.exec())

    @staticmethod
    def warning(parent, title, text, buttons=QtMessageBox.StandardButton.Ok, defaultButton=QtMessageBox.StandardButton.NoButton):
        return MessageBox._show(QtMessageBox.Icon.Warning, parent, title, text, buttons, defaultButton)

    @staticmethod
    def critical(parent, title, text, buttons=QtMessageBox.StandardButton.Ok, defaultButton=QtMessageBox.StandardButton.NoButton):
        return MessageBox._show(QtMessageBox.Icon.Critical, parent, title, text, buttons, defaultButton)

    @staticmethod
    def question(parent, title, text, buttons=QtMessageBox.StandardButton.Yes | QtMessageBox.StandardButton.No, defaultButton=QtMessageBox.StandardButton.No):
        return MessageBox._show(QtMessageBox.Icon.Question, parent, title, text, buttons, defaultButton)
