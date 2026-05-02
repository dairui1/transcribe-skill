# segments → SRT

ElevenLabs 和 Groq 返回的 `segments` 没现成 SRT，要自己渲染。`segments_to_srt(segments)` 已实现，本文档讲为什么这样实现。

## SRT 格式（标准复述）

```
<index>
HH:MM:SS,mmm --> HH:MM:SS,mmm
<text>

<index2>
HH:MM:SS,mmm --> HH:MM:SS,mmm
<text2>
```

- index 从 1 开始
- 时间戳用**逗号**分隔毫秒（不是点；点是 WebVTT）
- 块之间空一行
- 文件末尾要有一个换行

## 输入 segment 的两种约定

代码同时接受两种：
- `{startMs, endMs, text}`（毫秒整数；ElevenLabs 风格）
- `{start, end, text}`（秒浮点；Whisper / Groq 风格）

`segments_to_srt` 自动判断。

## 必要的清洗

实现里强制做了三件事：

1. **跳过空文本** segment（ASR 偶尔返回纯空白段）
2. **钳位 `endMs >= startMs`**（极小段可能反序，会被字幕播放器拒绝）
3. **strip 文本前后空白**

不做的：换行折行、字符数限制、说话人前缀——这些是字幕组工艺，不是 ASR skill 的职责。需要时另开 `interaction-skills/subtitle-formatting.md`。

## 已知陷阱

- **ElevenLabs `words` 不是 segments**——它返回 word-level 时间戳。要先 group 成句子（按 punctuation 或 word 间隔 > 0.5s 切）才能喂 segments_to_srt。当前 `_transcribe_elevenlabs` 直接传 words，效果是每个词一行——撞到这个问题时 self-heal `_transcribe_elevenlabs` 加 word-to-segment 聚合
- **Whisper segment 里的 `text` 经常带前导空格**——已经 strip 处理了
- **超长 segment（>10s）字幕播放体验差**——但这是 ASR 的事，不在渲染层补
