# video-to-tutorial-html

一个把本地视频（演讲 / 讲座 / 教程，任意语言）完整转换为**中文图文 HTML 教程**的技能（SKILL）。

完整流水线：`ffprobe 探测 → ffmpeg 提取音频与关键帧 → faster-whisper GPU 转录（含 Windows CUDA DLL 修复）→ 中文翻译（保留时间戳）→ 品牌化单文件 HTML 生成 → headless Chrome 视觉验收`。

## 流程图

```
 ┌─────────┐   ┌──────────┐   ┌──────────────────┐   ┌──────────┐
 │ 视频.mp4 │ → │ ffprobe  │ → │ ffmpeg 音频+关键帧 │ → │ 视觉内容  │
 └─────────┘   └──────────┘   └──────────────────┘   │ 逐帧分析  │
                                                     └────┬─────┘
 ┌──────────────┐   ┌──────────────┐   ┌──────────────────┴───┐
 │ 中文翻译 .md  │ ← │ 转录 .txt/.json│ ← │ faster-whisper (GPU) │
 └──────┬───────┘   └──────────────┘   └──────────────────────┘
        ↓
 ┌──────────────────┐   ┌────────────────────┐
 │ 单文件 HTML 教程  │ → │ Chrome 无头渲染 QA  │
 │ (SVG图标/VI配色)  │   │ (切片+隐藏章节渲染)  │
 └──────────────────┘   └────────────────────┘
```

## 文件结构

```
video-to-tutorial-html/
├── SKILL.md                        # 完整工作流（含全部踩坑修复）
├── agents/openai.yaml              # 技能 UI 元数据
├── scripts/
│   ├── transcribe.py               # GPU 转录（自动修复 cublas/cudnn、语言探测、双格式输出）
│   └── qa_render.py                # 无头 Chrome QA（超高页截断→隐藏章节渲染、PIL 切片、内容底检测）
├── references/
│   └── pipeline-notes.md           # 真实 28 分钟视频实战的全部踩坑与修复记录
└── assets/
    └── tutorial-template.html      # 已验收的教程设计系统（复制后替换内容即用）
```

## 环境要求

- Python ≥ 3.10，`pip install faster-whisper`（GPU 需 `nvidia-cublas-cu12`、`nvidia-cudnn-cu12`）
- ffmpeg / ffprobe（PATH 中可用）
- Chrome 或 Edge（视觉 QA 用）
- 可选：`gh` CLI（发布到 GitHub）

## 快速使用

```bash
# 探测
ffprobe -v error -show_entries format=duration,size 视频.mp4

# 提取音频（16kHz 单声道）与关键帧（每15秒一帧）
ffmpeg -y -v error -i 视频.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le work/audio.wav
ffmpeg -y -v error -i 视频.mp4 -vf "fps=1/15,scale=640:-1" -q:v 5 work/frames/f_%04d.jpg

# GPU 转录（脚本自动注入 CUDA DLL、探测语言）
python scripts/transcribe.py work/audio.wav --language auto --out work/

# 视觉 QA（自动切片、超高页自动隐藏前部章节渲染尾部）
python scripts/qa_render.py work/教程.html --out work/render/ --hide c1,c2,c3
```

## 已解决的典型坑（详见 references/pipeline-notes.md）

- `torch.cuda.is_available()` 为 False ≠ 没有 GPU，应查 `ctranslate2.get_cuda_device_count()`
- `cublas64_12.dll not found`：装 nvidia pip 包后必须**把 bin 目录前置到 PATH**（`os.add_dll_directory` 对 ctranslate2 无效）
- 本地代理挂掉导致 pip 失败：清掉 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY` 后走清华镜像
- 视频文件名是中文 ≠ 内容是中文：先 60 秒自动探测语言再全片转录
- Chrome 无头截图上限 ~16384px：超高页面用"隐藏前部章节"方案渲染尾部
- 教程 HTML 中不使用任何 emoji，图标统一为内联 SVG sprite（38 个定义 / 38 处引用零冗余）

## License

MIT
