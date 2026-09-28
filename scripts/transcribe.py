#!/usr/bin/env python3
"""GPU transcription with faster-whisper, hardened for Windows CUDA.

Handles the three failure modes hit in practice:
  1. cublas64_12.dll / cudnn64_9.dll missing        -> pip install + PATH prepend
  2. os.add_dll_directory() ignored by ctranslate2   -> PATH is prepended instead
  3. wrong language forced from the video title      -> optional 60 s auto-probe

Usage:
  python transcribe.py audio.wav [--language auto|en|zh|...] [--model small]
                          [--compute float16|int8] [--out DIR] [--beam 5]

Outputs: transcript.txt ("[12.3-45.6] text" lines) + transcript.json.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

NVIDIA_SUBDIRS = ["cublas", "cudnn", "cuda_nvrtc", "cufft", "curand"]


def repair_cuda_dlls() -> None:
    """Make cuBLAS/cuDNN DLLs importable by ctranslate2 on Windows.

    ctranslate2 loads CUDA DLLs with LoadLibrary, which searches PATH —
    os.add_dll_directory() alone is NOT sufficient. Prepending the pip
    nvidia/* binaries to PATH before importing faster-whisper fixes it.
    """
    import site

    added = []
    for sp in dict.fromkeys(site.getsitepackages() + [site.getusersitepackages()]):
        for sub in NVIDIA_SUBDIRS:
            bin_dir = Path(sp) / "nvidia" / sub / "bin"
            if bin_dir.is_dir():
                os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
                added.append(str(bin_dir))
    if added:
        print(f"[dll] injected {len(added)} NVIDIA bin dirs into PATH", file=sys.stderr)


def ensure_pkgs() -> None:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        _pip_install("faster-whisper")


def _pip_install(*pkgs: str) -> None:
    """pip install with dead-local-proxy workaround + CN mirror fallback."""
    env = {k: v for k, v in os.environ.items() if k.lower() not in
           ("http_proxy", "https_proxy", "all_proxy")}
    cmd = [sys.executable, "-m", "pip", "install", "-q", *pkgs]
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        mirror = "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"
        subprocess.run(cmd + list(mirror), env=env, check=True)


def ensure_cuda_runtime() -> None:
    """Install cuBLAS/cuDNN wheels if the DLLs are not already available."""
    import site

    have = any((Path(sp) / "nvidia" / "cublas" / "bin").is_dir()
               for sp in site.getsitepackages() + [site.getusersitepackages()])
    if not have:
        print("[dll] installing nvidia-cublas-cu12 nvidia-cudnn-cu12 ...", file=sys.stderr)
        _pip_install("nvidia-cublas-cu12", "nvidia-cudnn-cu12")


def pick_device() -> tuple[str, str]:
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception as exc:  # noqa: BLE001
        print(f"[gpu] probe failed ({exc}); falling back to CPU", file=sys.stderr)
    return "cpu", "int8"


def probe_language(model, audio: str) -> str:
    segs, info = model.transcribe(audio, language=None, beam_size=1)
    for _ in zip(segs, range(3)):  # consume only the first few segments
        break
    print(f"[lang] detected={info.language} p={info.language_probability:.2f}",
          file=sys.stderr)
    return info.language


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--language", default="auto", help="auto probes first 60s")
    ap.add_argument("--model", default="small",
                    help="small fits 2GB VRAM fp16; large-v3 does not")
    ap.add_argument("--compute", default=None, help="float16|int8 (default: by device)")
    ap.add_argument("--out", default=".", help="output directory")
    ap.add_argument("--beam", type=int, default=5)
    args = ap.parse_args()

    ensure_pkgs()
    ensure_cuda_runtime()
    repair_cuda_dlls()

    from faster_whisper import WhisperModel

    device, default_compute = pick_device()
    compute = args.compute or default_compute
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    model = WhisperModel(args.model, device=device, compute_type=compute)
    print(f"[model] {args.model} on {device}/{compute} loaded in {time.time()-t0:.1f}s",
          file=sys.stderr)

    language = None if args.language == "auto" else args.language
    if args.language == "auto":
        language = probe_language(model, args.audio)

    segs, info = model.transcribe(
        args.audio, language=language, beam_size=args.beam, vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300, speech_pad_ms=200),
    )

    rows, t0 = [], time.time()
    with open(out / "transcript.txt", "w", encoding="utf-8") as f:
        for s in segs:
            f.write(f"[{s.start:.1f}-{s.end:.1f}] {s.text}\n")
            rows.append({"start": s.start, "end": s.end, "text": s.text})
    (out / "transcript.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    dur = rows[-1]["end"] if rows else 0
    rt = dur / max(time.time() - t0, 0.1)
    print(f"[done] {len(rows)} segments, audio {dur:.0f}s, "
          f"{time.time()-t0:.0f}s ({rt:.1f}x realtime), lang={language}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
