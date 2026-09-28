---
name: video-to-tutorial-html
description: >
  Turn a local video (lecture / talk / tutorial, any language) into a polished
  structured Chinese HTML tutorial: probe with ffprobe, extract audio with
  ffmpeg, transcribe with faster-whisper on GPU (including Windows CUDA DLL
  repair), sample keyframes to map slides, translate the transcript to Chinese
  with timestamps, generate a branded single-file HTML document (Anthropic VI
  palette, inline SVG icon sprite, sidebar nav, progress bar, terminal blocks,
  prompt bubbles), and run visual QA with headless Chrome (tall-screenshot
  slicing + section hiding for pages beyond the 16384px render cap). Use when
  the user asks to 转录视频 / transcribe a video / 视频转教程 / translate a
  talk into Chinese / 生成图文教程 / make an illustrated HTML tutorial from a
  recording. Triggers on video/audio transcription-to-tutorial requests.
---

# Video → Illustrated Chinese HTML Tutorial

Convert one video into three deliverables: (1) timestamped transcript,
(2) full Chinese Markdown translation, (3) a branded single-file HTML
tutorial — then visually verify it. Work in a scratch dir next to the video:
`<video_dir>/<topic>_work/`.

## Quick start (verified pipeline)

```bash
# 0. Probe
ffprobe -v error -show_entries format=duration,size VIDEO.mp4

# 1. Audio + keyframes (parallel)
ffmpeg -y -v error -i VIDEO.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le work/audio.wav
mkdir -p work/frames
ffmpeg -y -v error -i VIDEO.mp4 -vf "fps=1/15,scale=640:-1" -q:v 5 work/frames/f_%04d.jpg

# 2. GPU transcription (script handles CUDA DLL repair; see notes below)
python scripts/transcribe.py work/audio.wav --language auto --out work/

# 3. Visual QA (script slices tall screenshots & renders hidden-section tails)
python scripts/qa_render.py work/Tutorial.html --out work/render/
```

## Step 1 — Probe the environment

1. `ffprobe` the video: duration decides model size and wall-clock budget.
2. Detect GPU the right way: `python -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"`.
   Do NOT trust `torch.cuda.is_available()` — a CPU-only torch wheel reports
   False even on CUDA machines.
3. Check cached HF models: `ls ~/.cache/huggingface/hub | grep -i whisper`.
   If only `small` is cached and VRAM is tight, use it (`small` fp16 ≈ 4.5x
   realtime on an MX450; a 28-min video transcribed in ~6 min).

## Step 2 — Extract audio & keyframes

- Audio: 16 kHz mono WAV (`-ac 1 -ar 16000`) — exactly what faster-whisper expects.
- Keyframes: 1 frame / 15 s, `scale=640:-1 -q:v 5` → ~110 frames for 28 min.
  Read a spread (start / each new slide / end) to map on-screen slides before
  writing anything; the transcript alone misses slide content and examples.

## Step 3 — GPU transcription with faster-whisper

`scripts/transcribe.py` does: DLL repair → model load (fp16, CUDA) →
transcribe (beam_size=5, VAD 300ms, timestamps) → `transcript.txt` +
`transcript.json`. Known pitfalls (all hit in practice, see
`references/pipeline-notes.md` for detail):

- `RuntimeError: Library cublas64_12.dll is not found` →
  `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`, then **prepend** the
  `.../site-packages/nvidia/{cublas,cudnn,cuda_nvrtc}/bin` dirs to
  `os.environ["PATH"]` before importing faster-whisper.
  `os.add_dll_directory()` does NOT work for ctranslate2's LoadLibrary.
- pip proxy dead (`127.0.0.1:7890 refused`) → unset `HTTP_PROXY HTTPS_PROXY
  ALL_PROXY` and install via `-i https://pypi.tuna.tsinghua.edu.cn/simple`.
- Language: never trust the filename — probe 60 s with `language=None` first.
  A Chinese-titled video can be an English talk; forced `language="zh"` on
  English audio yields garbage.
- 2 GB VRAM: `small` fp16 fits (~1 GB); `medium` int8 is borderline; `large-v3`
  will not fit.

## Step 4 — Translate to Chinese (Markdown)

- Keep every `[start-end]` timestamp so readers can locate the moment.
- First person, spoken register; Q&A marks speaker turns (提问者 / 演讲者).
- Fix ASR mishears contextually, list corrections in an appendix:
  `quad code→Claude Code`, `no JS→Node.js`, `Dalton eyes themes→色盲友好主题`,
  `dox→文档`.
- Structure with H2 sections following the talk's actual arc, not uniform
  paragraphs.

## Step 5 — Generate the HTML tutorial

Start from `assets/tutorial-template.html` (the proven design system) and
replace content. Hard requirements — the checklist that survived review:

- Single self-contained file; inline CSS/JS/SVG sprite; zero external assets.
- **No emoji anywhere** — icons come from the inline `<symbol>` sprite
  (stroke 1.7, round caps); verify with a script that every `href="#i-*"` has
  a matching symbol and none are unused. Typographic `→ § ——` are fine.
- Anthropic VI palette only: paper `#FAF9F5`, ivory `#F0EEE6`, slate `#141413`,
  crail `#D97757`/`#C15F3C`, book cloth `#CC785C`, kraft `#D4A27F`,
  manilla `#EBDBBC`. Callout tints derive from these — no foreign hues.
  Font stacks front-load Styrene / Tiempos / Berkeley Mono.
- Components: fixed sidebar TOC with scroll-spy, top progress bar, back-to-top,
  mobile drawer, hero with stat row, terminal blocks (traffic dots + slate bg),
  chat-style prompt bubbles with blinking cursor, quote blocks with big `"`
  glyph, four-tone callouts, flow diagrams with SVG arrows, matrix tables,
  kbd chips, Q&A cards, vertical roadmap, CSS-drawn checkmark list.
- Brand text: logo is "Claude Code" (not the event name); keep event-name
  references like "Code w/ Claude" in kicker/footer as factual citations.
- Content: every chapter must cover the corresponding transcript segment;
  preserve slide examples (real prompt templates, commands) verbatim; keep
  speaker quotes as blockquotes with attribution.

## Step 6 — Visual QA with headless Chrome

`scripts/qa_render.py` renders + slices + verifies. Non-obvious traps:

- Use `--headless=new --hide-scrollbars --force-device-scale-factor=1`;
  `--screenshot` must be an absolute Windows path (relative paths fail).
- Chrome caps window height (~16384 px): pages taller than that get truncated.
  Fix: render a temp copy with earlier sections `display:none` to capture the
  tail, then slice with PIL and detect real content bottom via a numpy row scan.
- Read top + middle + tail slices at minimum; a 15 KB PNG is a blank render
  (anchor-fragment scrolling does not work in `--screenshot` mode).

## Step 7 — Package & publish (optional)

1. Validate: `python "$CODEX_HOME/skills/skill-creator/scripts/quick_validate.py" <skill-dir>`.
2. `git init && git add -A && git commit`, then
   `gh repo create <name> --public --source=. --push`.
3. README: pipeline diagram, requirements (ffmpeg / Python / faster-whisper /
   Chrome), usage, file map.

## Resources

- `scripts/transcribe.py` — full GPU transcription script (DLL repair, probe,
  timestamps, JSON+TXT out). Run, don't read.
- `scripts/qa_render.py` — headless Chrome QA: render, slice, content-bottom
  detection, hidden-section tail rendering.
- `references/pipeline-notes.md` — every pitfall and its fix encountered while
  building this pipeline end-to-end on a real 28-min talk. Read when anything
  fails.
- `assets/tutorial-template.html` — the finished tutorial design system used
  as the Step-5 base (copy, then replace content).
