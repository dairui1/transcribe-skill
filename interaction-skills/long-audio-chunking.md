# 长音频切片与拼接

ASR 的硬墙：

| 引擎 | 单文件上限 |
|---|---|
| ElevenLabs Scribe | ~25 分钟 / 文件（实测；超过会报 file too large 或 timeout） |
| Groq Whisper | 25 MB / 文件 |
| mlx-whisper（本地） | 无硬墙，但 30 分钟以上 RAM 占用爬升明显 |

播客经常 1-3 小时，必撞。流程：

```python
from helpers import chunk_audio, transcribe, stitch_segments, segments_to_srt
from pathlib import Path

audio = Path("out/episode.m4a")
chunks = chunk_audio(audio, Path("out/chunks"), chunk_sec=20 * 60)  # 20 分钟一片

results = []
for c in chunks:
    r = transcribe(c.path, engine="elevenlabs")
    results.append((c.index, r["segments"]))

merged = stitch_segments(results, chunk_sec=20 * 60)
srt = segments_to_srt(merged)
Path("out/episode.srt").write_text(srt)
```

## 为什么 chunk_sec 推荐 20 分钟（不是 25）

留 5 分钟 buffer——ElevenLabs 偶尔在边界 timeout，Groq 25MB 限制对高码率 m4a 是 22 分钟左右。

## 为什么用 ffmpeg `-c copy` 不重编码

切片只改容器、不改编码 = 几秒搞定 + 无质量损失。代价是切点必须在 keyframe，可能切到说话中间一两秒。ASR 处理这种边界本就稳健（重叠的词在拼接时会重复出现 1-2 个，可接受）。

如果你需要**精确切到静音处**，要先用 `ffmpeg -af silencedetect` 找静音点再分段——那时再 self-heal `chunk_audio` 加 silence-aware 模式，并把这一段加到本文件。

## stitch 时间戳偏移

每个 chunk 的 ASR 结果时间戳是从 0 开始的，必须加 `chunk_index * chunk_sec * 1000` ms 才能拼回原音频的时间轴。`stitch_segments` 已经做了这件事。

## 已知陷阱

- **ffmpeg segment 切片输出文件按 `chunk-000.m4a` 命名**——文件系统排序必须 zero-padded 否则 `chunk-10` 会排到 `chunk-2` 前面
- **chunk 数量大时 ASR 并发**：ElevenLabs 免费档 1 并发、付费 5；Groq 30 RPM。同步循环够用，撞到 rate limit 再加 asyncio + sleep
- **mlx-whisper 长文件不必切**：除非内存压力。实测 M2 Pro 16GB 跑 2 小时 m4a 没问题
