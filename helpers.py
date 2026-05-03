"""
transcribe-skill helpers — 起步实现，agent 可读可改。

三个原语：
  resolve_source(url)   URL → 音频 URL + 元数据
  download_audio(...)   下载到本地
  transcribe(...)       本地音频 → 文本 + SRT

清洗不在 helpers——agent 自己读 transcript（必要时抓 episode_context）
直接产出 cleaned text。理由见 SKILL.md「清洗」一节。

通用机制（来自其他模块，re-export 方便用）：
  chunk_audio / stitch_segments / segments_to_srt   见 audio.py + interaction-skills/

撞到 helpers 不覆盖的事，**直接改这个文件**，并把学到的怪癖写进
domain-skills/<平台>.md 或 interaction-skills/<机制>.md。
"""

import json
import os
import subprocess
from pathlib import Path

import httpx

from sources import Source, resolve as resolve_source  # noqa: F401
from audio import chunk_audio, stitch_segments, segments_to_srt  # noqa: F401


def download_audio(audio_url: str, dest: Path) -> Path:
    """流式下载到 dest。dest 是完整路径含扩展名。"""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", audio_url, follow_redirects=True, timeout=None) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    return dest


def transcribe(
    audio_path: Path,
    engine: str = "mlx-whisper",
    language: str | None = None,
    diarize: bool = False,
    num_speakers: int | None = None,
) -> dict:
    """
    本地音频 → {text, srt, segments}。开 diarize 时 segments 多带 "speaker" 字段。

    engine:
      "mlx-whisper" — 本地子进程，需先 `uv tool install mlx-whisper`，仅 Apple Silicon
      "elevenlabs"  — HTTP，需 ELEVENLABS_API_KEY；唯一支持 diarize 的 engine
      "groq"        — HTTP，需 GROQ_API_KEY，最快
    """
    audio_path = Path(audio_path)
    if diarize and engine != "elevenlabs":
        raise ValueError(f"diarize=True 只支持 engine='elevenlabs'，当前 {engine!r}")
    if engine == "mlx-whisper":
        return _transcribe_mlx(audio_path, language)
    if engine == "elevenlabs":
        return _transcribe_elevenlabs(audio_path, language, diarize, num_speakers)
    if engine == "groq":
        return _transcribe_groq(audio_path, language)
    raise ValueError(f"unknown engine: {engine}")


def _transcribe_mlx(audio: Path, language: str | None) -> dict:
    out_dir = audio.parent / f".{audio.stem}.mlx"
    out_dir.mkdir(exist_ok=True)
    cmd = ["mlx_whisper", str(audio), "--output-dir", str(out_dir), "--output-format", "all"]
    if language:
        cmd += ["--language", language]
    subprocess.run(cmd, check=True)
    txt = (out_dir / f"{audio.stem}.txt").read_text()
    srt = (out_dir / f"{audio.stem}.srt").read_text()
    json_path = out_dir / f"{audio.stem}.json"
    segments = json.loads(json_path.read_text())["segments"] if json_path.exists() else []
    return {"text": txt, "srt": srt, "segments": segments}


def _transcribe_elevenlabs(
    audio: Path,
    language: str | None,
    diarize: bool = False,
    num_speakers: int | None = None,
) -> dict:
    api_key = os.environ["ELEVENLABS_API_KEY"]
    files = {"file": audio.open("rb")}
    data = {"model_id": "scribe_v1"}
    if language:
        data["language_code"] = language
    if diarize:
        data["diarize"] = "true"
        if num_speakers is not None:
            data["num_speakers"] = str(num_speakers)
    r = httpx.post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": api_key},
        files=files,
        data=data,
        timeout=600,
    )
    r.raise_for_status()
    j = r.json()
    words = j.get("words", [])
    segments = _words_to_speaker_segments(words) if diarize else words
    return {"text": j["text"], "srt": "", "segments": segments}


def _words_to_speaker_segments(words: list[dict]) -> list[dict]:
    """
    把 ElevenLabs 的 word-level 输出按 speaker_id 合并成段落 segments。
    输入 word: {text, start, end, speaker_id, type?}
    输出 segment: {start, end, speaker, text}
    遇到 speaker 切换或同一 speaker 内 gap > 1.5s 切段。
    """
    segs: list[dict] = []
    cur: dict | None = None
    GAP = 1.5
    for w in words:
        spk = w.get("speaker_id") or w.get("speaker") or "unknown"
        wt = w.get("text", "")
        ws, we = w.get("start"), w.get("end")
        if ws is None or we is None:
            if cur is not None:
                cur["text"] += wt
            continue
        if cur is None or spk != cur["speaker"] or ws - cur["end"] > GAP:
            if cur is not None:
                cur["text"] = cur["text"].strip()
                segs.append(cur)
            cur = {"start": ws, "end": we, "speaker": spk, "text": wt}
        else:
            cur["end"] = we
            cur["text"] += wt
    if cur is not None:
        cur["text"] = cur["text"].strip()
        segs.append(cur)
    return segs


def _transcribe_groq(audio: Path, language: str | None) -> dict:
    api_key = os.environ["GROQ_API_KEY"]
    files = {"file": (audio.name, audio.open("rb"))}
    data = {"model": "whisper-large-v3", "response_format": "verbose_json"}
    if language:
        data["language"] = language
    r = httpx.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        files=files,
        data=data,
        timeout=600,
    )
    r.raise_for_status()
    j = r.json()
    return {"text": j["text"], "srt": "", "segments": j.get("segments", [])}


