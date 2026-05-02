"""
音频处理通用机制：切片、SRT 渲染。

设计：
- chunk_audio: ffmpeg segment 切片，无重编码（-c copy），毫秒级偏移
- segments_to_srt: ASR segments → 标准 SRT 字符串

撞到边界（chunk 切到说话中间、SRT 行长溢出等）时改这里，
并把"为什么这样切"写进 interaction-skills/<机制>.md。
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AudioChunk:
    index: int
    path: Path
    offset_ms: int


def chunk_audio(audio_path: Path, out_dir: Path, chunk_sec: int) -> list[AudioChunk]:
    """
    用 ffmpeg segment 切片。无重编码（-c copy），秒级
    切但毫秒级偏移已知（chunk_sec * 1000 * index）。

    长音频转录前用这个，转完后按 offset_ms 偏移每个 chunk 的 segment 时间戳，
    再 concat 成完整 transcript。
    """
    audio_path = Path(audio_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if chunk_sec <= 0:
        raise ValueError(f"chunk_sec 必须 > 0，给的是 {chunk_sec}")

    ext = audio_path.suffix or ".audio"
    pattern = str(out_dir / f"chunk-%03d{ext}")

    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(audio_path),
            "-f", "segment",
            "-segment_time", str(chunk_sec),
            "-c", "copy",
            "-reset_timestamps", "1",
            pattern,
        ],
        check=True,
    )

    files = sorted(p for p in out_dir.iterdir() if p.name.startswith("chunk-"))
    if not files:
        raise RuntimeError("ffmpeg 没产出任何 chunk 文件")

    return [AudioChunk(index=i, path=p, offset_ms=i * chunk_sec * 1000) for i, p in enumerate(files)]


def stitch_segments(chunk_results: list[tuple[int, list[dict]]], chunk_sec: int) -> list[dict]:
    """
    把多个 chunk 的 segments 按 offset 合并成单一 segment 列表。

    chunk_results: [(chunk_index, segments_from_that_chunk), ...]
    每个 segment 字典需要至少含 `start` / `end` / `text`（秒）或 `startMs` / `endMs`。
    """
    out = []
    for index, segs in sorted(chunk_results):
        offset_ms = index * chunk_sec * 1000
        for s in segs:
            new = dict(s)
            if "startMs" in new:
                new["startMs"] = int(new["startMs"]) + offset_ms
                new["endMs"] = int(new["endMs"]) + offset_ms
            elif "start" in new:
                new["start"] = float(new["start"]) + offset_ms / 1000
                new["end"] = float(new["end"]) + offset_ms / 1000
            out.append(new)
    return out


def segments_to_srt(segments: list[dict]) -> str:
    """
    segments → SRT 字符串。

    segment 必须有 text + (startMs/endMs 或 start/end)。
    自动跳过空文本，钳位 endMs >= startMs，去前后空白。
    """
    cleaned = []
    for s in segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        if "startMs" in s:
            start_ms = max(0, int(s["startMs"]))
            end_ms = max(start_ms, int(s["endMs"]))
        else:
            start_ms = max(0, int(float(s["start"]) * 1000))
            end_ms = max(start_ms, int(float(s["end"]) * 1000))
        cleaned.append((start_ms, end_ms, text))

    parts = []
    for i, (start, end, text) in enumerate(cleaned, 1):
        parts.append(f"{i}\n{_fmt(start)} --> {_fmt(end)}\n{text}")
    return "\n\n".join(parts) + ("\n" if cleaned else "")


def _fmt(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
