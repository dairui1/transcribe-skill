# diarization（说话人分离）

把 transcript 切成 "谁在何时说了什么"。本 skill 当前只在 ElevenLabs Scribe 上实现。

## 用法

```python
from helpers import resolve_source, download_audio, transcribe
from pathlib import Path

src = resolve_source(url)
audio = download_audio(src.audio_url, Path(f"./out/{src.title}.m4a"))
r = transcribe(audio, engine="elevenlabs", diarize=True)
# 知道说话人数量时建议传 num_speakers，准确率更高：
# r = transcribe(audio, engine="elevenlabs", diarize=True, num_speakers=2)

for seg in r["segments"]:
    print(f"[{seg['speaker']}] {seg['text']}")
```

`diarize=True` 时 `segments` 形状变为 `{start, end, speaker, text}`（按说话人合并过的段落）。
`diarize=False` 时仍是 ElevenLabs 原生 word-level 列表。

## 三档方案对比

选 engine 时的取舍：

| 方案 | 支持 | 成本 | 隐私 | 易用 |
|---|---|---|---|---|
| **ElevenLabs Scribe** | `diarize=true` 一参数 | 按分钟付费 | 上传到云 | ⭐ 当前实现 |
| pyannote.audio + whisper | 本地两遍跑+合并 | 免费 | 全本地 | 需 HF token、接受 license |
| WhisperX | 缝好的本地 pipeline | 免费 | 全本地 | 依赖重，与 mlx-whisper 路径不兼容 |

要本地方案再回来扩 `helpers.py`，加新 engine 或新原语 `diarize_local(audio) -> [(start, end, speaker)]`，再写一个 `merge_speakers_into_segments(segments, diar)` 把说话人贴回 whisper segments。

## 段落合并策略（已实现）

ElevenLabs 返回 word-level，`_words_to_speaker_segments` 按以下规则合并：

- 同一 `speaker_id` 连续的 word 拼成一段
- 切段触发条件：speaker 切换 **或** 同一 speaker 内 word 间 gap > 1.5s
- gap 阈值是经验值，会议长沉默/播客插播音乐时可调大

## SRT 输出

当前 `result["srt"]` 在 elevenlabs engine 下为空字符串。要带说话人的 SRT，自己拼：

```python
def speaker_srt(segments):
    lines = []
    for i, s in enumerate(segments, 1):
        lines += [str(i), f"{_ts(s['start'])} --> {_ts(s['end'])}",
                  f"[{s['speaker']}] {s['text']}", ""]
    return "\n".join(lines)
```

`_ts` 用 `audio.py` 里 `segments_to_srt` 已有的时间戳格式。

## 把 speaker_id 换成真名

ElevenLabs 返回的是 `speaker_0` / `speaker_1` 这种匿名 ID。要换成真名：

1. 抓 episode 上下文（`r.jina.ai/<URL>`），找到嘉宾/主持人列表
2. 听首段判断哪个 ID 对应谁（开头通常自报家门）
3. 简单 dict 映射后写入 `.cleaned.txt`

这一步属于「清洗」环节，按 SKILL.md 规则由 agent 直接做，不调外部 LLM。

## 已知坑

- **`num_speakers="auto"` 不是合法值**——不传该字段就是 auto；传了就必须是整数
- **极短发言会被吞**——单 word 切到独立 speaker_id 时段落会很碎，必要时后处理把 < 0.5s 的孤立段并到相邻段
- **重叠说话**：Scribe 不分离重叠语音，会归到主导那个 speaker
