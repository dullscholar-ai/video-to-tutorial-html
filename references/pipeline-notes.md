# Pipeline Notes — pitfalls encountered on a real 28-min run

Recorded while converting a 28-min bilingual-labelled English talk
(`claude的工程级用法.mp4`, 181 MB) into transcript + translation + HTML
tutorial. Every entry below was actually hit; the fix is the one that worked.

## Environment detection

| Symptom | Reality | Fix |
|---|---|---|
| `torch.cuda.is_available()` → False on a CUDA laptop | CPU-only torch wheel was installed; torch is irrelevant to faster-whisper anyway | Check `ctranslate2.get_cuda_device_count()` instead |
| Only `models--Systran--faster-whisper-small` cached | 2 GB VRAM (MX450) rules out large-v3 fp16 (~4.7 GB) | Use `small` fp16 (~1 GB); 1677 s audio transcribed in 374 s (~4.5× realtime) |

## CUDA DLL repair (Windows)

- First GPU run dies with `RuntimeError: Library cublas64_12.dll is not found`.
- `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` fetches the wheels into
  `site-packages/nvidia/{cublas,cudnn,cuda_nvrtc}/bin/`.
- **`os.add_dll_directory(bin)` does NOT work** — ctranslate2 loads via
  `LoadLibrary`, which ignores Python's added dirs. What works: prepend the
  bin dirs to `os.environ["PATH"]` **before importing faster_whisper**.
- `site.getsitepackages()[0]` may point at the base prefix, not Lib/site-packages;
  iterate all candidates and take the dirs that exist.

## pip behind a dead local proxy

- Env has `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY=http://127.0.0.1:7890`; proxy off →
  `NewConnectionError ... [WinError 10061]`.
- `pip install --proxy=""` does NOT override env vars. Working recipe:
  `env`-stripped subprocess + fallback mirror
  `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkgs>`.
- `nvidia.cublas.__file__` is None (namespace package) — locate DLLs by
  walking `site-packages/nvidia/*/bin`, not by module path.

## Transcription correctness

- **Never trust the filename.** `claude的工程级用法.mp4` is an English talk
  (Boris Cherny at the "Code w/ Claude" event). Forcing `language="zh"` on it
  produced garbage ("HelloHelloHelloI'm Boris..."). Probe first:
  transcribe with `language=None`, read `info.language` (detected `en`, p=0.99),
  then run the full pass with the detected language.
- The video carries burned-in Chinese subtitles; keyframes at 1/15 s expose
  them plus the slide decks — both are content the audio transcript misses
  (slide examples like `Propose a few fixes for issue #8732`).
- ASR mishears to fix during translation: `quad code`→Claude Code,
  `no JS`→Node.js, `Dalton eyes themes`→色盲友好 (colorblind) themes,
  `a dox`→a doc, `adentropic`→at Anthropic.

## HTML generation

- Design system that passed user review (twice): Anthropic VI palette
  (paper `#FAF9F5`, ivory `#F0EEE6`, slate `#141413`, crail `#D97757`,
  book cloth `#CC785C`, kraft `#D4A27F`, manilla `#EBDBBC`), serif headings,
  sidebar TOC with scroll-spy, SVG icon sprite (stroke 1.7), zero emoji —
  the user explicitly banned emoji as "幼稚符号".
- Callout CSS trap: `.co b{display:block}` (intended for the callout title)
  also blocks *inline* bold inside body paragraphs → ugly line breaks.
  Fix: `.co .bd>b:first-child{display:block}` + `.co p b{display:inline}`.
- Icon integrity: 38 symbols defined / 38 used after pruning; script-check
  `href="#i-*"` vs `<symbol id>` before shipping.

## Headless Chrome QA

- `--screenshot=render/x.png` (relative) fails with `系统找不到指定的路径`;
  pass an absolute Windows path.
- `file:///...#c6` does not scroll in `--screenshot` mode → those shots are
  blank (~15 KB). Don't use anchors; hide sections instead.
- Window height caps near 16384 px: a 19 000 px page renders truncated.
  Recipe: `--force-device-scale-factor=0.8 --window-size=1800,16384` to reach
  ~20 480 logical px, or render a temp copy with `#c1..#cN{display:none}` and
  shoot the tail at normal scale.
- Detect real content bottom: numpy row scan vs. the trailing background row
  (`rows.max()+40`); slice at 2400 px with PIL for review.
- A slice that is entirely background is fine (window taller than page);
  a full PNG under ~20 KB means the render itself failed.

## Skill packaging & GitHub

- `gh auth status` confirmed keyring login; `gh repo create <name> --public
  --source=. --push` publishes the skill folder in one step.
- Skill structure follows skill-creator: YAML frontmatter (name/description
  with explicit triggers), workflow body ≤ ~500 lines, scripts run-without-
  reading, one reference file for the full pitfall journal, the finished
  tutorial HTML as a copy-and-replace template asset.
