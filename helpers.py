"""
transcribe-skill helpers — 起步实现，agent 可读可改。

四个原语：
  resolve_source(url)   URL → 音频 URL + 元数据
  download_audio(...)   下载到本地
  transcribe(...)       本地音频 → 文本 + SRT
  cleanup(...)          ASR 文本 → 清洗后文本

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


def transcribe(audio_path: Path, engine: str = "mlx-whisper", language: str | None = None) -> dict:
    """
    本地音频 → {text, srt, segments}。

    engine:
      "mlx-whisper" — 本地子进程，需先 `uv tool install mlx-whisper`，仅 Apple Silicon
      "elevenlabs"  — HTTP，需 ELEVENLABS_API_KEY
      "groq"        — HTTP，需 GROQ_API_KEY，最快
    """
    audio_path = Path(audio_path)
    if engine == "mlx-whisper":
        return _transcribe_mlx(audio_path, language)
    if engine == "elevenlabs":
        return _transcribe_elevenlabs(audio_path, language)
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


def _transcribe_elevenlabs(audio: Path, language: str | None) -> dict:
    api_key = os.environ["ELEVENLABS_API_KEY"]
    files = {"file": audio.open("rb")}
    data = {"model_id": "scribe_v1"}
    if language:
        data["language_code"] = language
    r = httpx.post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": api_key},
        files=files,
        data=data,
        timeout=600,
    )
    r.raise_for_status()
    j = r.json()
    return {"text": j["text"], "srt": "", "segments": j.get("words", [])}


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


def cleanup(transcript: str, episode_context: str | None = None, model: str = "gpt-4.1-mini") -> str:
    """
    保守清洗 ASR 文本。只修明显错误：标点、人名/专有名词、重复词。
    不改写、不总结、不添内容。

    episode_context: 节目页面文本（agent 用 r.jina.ai/<url> 抓即可），
      用来把 ASR 听错的人名/专有名词修正成 episode 里出现过的写法。
    """
    from openai import OpenAI

    client = OpenAI()
    sys_prompt = (
        "你是一个保守的转录文本清洗员。只做：标点修正、明显的人名/专有名词错字"
        "（结合上下文 context 里出现过的写法）、去掉口癖式重复。"
        "禁止：改写、总结、添加内容、删段。输出仅清洗后的文本，无解释。"
    )
    user = f"<context>\n{episode_context or ''}\n</context>\n<transcript>\n{transcript}\n</transcript>"
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}],
    )
    return r.choices[0].message.content or ""
