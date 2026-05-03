---
name: transcribe
description: 把任意视频/音频源（YouTube、播客、直链音频、本地文件）转录成文本与 SRT，并可选地用节目页面上下文清洗 ASR 结果。当用户分享视频/音频 URL、要字幕、要文字稿、要清洗 ASR 结果时触发。
---

# transcribe-skill

操作目标：各种视频/音频源 + 本地音频文件。
传输：HTTP（httpx）+ 子进程（yt-dlp / mlx_whisper）。

**第一件事：读 [helpers.py](./helpers.py)**——它定义了三个原语：`resolve_source` / `download_audio` / `transcribe`。

清洗不是 helpers 的事，由 agent 自己做（见下文「清洗」一节）。

## 三条不可破规则

本 skill 遵循 [meta-skill SPEC](https://github.com/dairui1/meta-skill/raw/main/SPEC.md)。简短复述：

1. **Self-heal**：helpers 不全时**直接改 `helpers.py`**。比如某平台 yt-dlp 抽不到音频，写一个平台特化的解析函数加进去。
2. **双层 sub-skills**：
   - `interaction-skills/`：通用机制——长音频切片、语言检测、SRT 对齐、清洗策略…
   - `domain-skills/`：具体平台/对象——小宇宙、Apple Podcasts、YouTube 频道、某个播客的术语表…
3. **Contribute back**：学到非显然的事必须写成 sub-skill。值得写：私有 API、稳定 selector、平台怪癖、必要 wait 的原因、陷阱。不该写：流水账、密钥、用户名。

## 典型流程

```python
from helpers import resolve_source, download_audio, transcribe
from pathlib import Path

src = resolve_source("https://www.xiaoyuzhoufm.com/episode/...")
audio = download_audio(src.audio_url, Path(f"./out/{src.title}.m4a"))
result = transcribe(audio, engine="mlx-whisper")  # 或 "elevenlabs" / "groq"
Path(f"./out/{src.title}.srt").write_text(result["srt"])
Path(f"./out/{src.title}.txt").write_text(result["text"])
```

## 清洗

**ASR 输出必须清洗**——raw transcript 没标点、有错字、口癖密布，几乎不可读。
**清洗由你（agent）直接做，不调外部 LLM API**——你本就是 LLM，多套一层调用是冗余、又多个 key 依赖、又隔着网络。

### 通用流程

1. **读** transcript 文件
2. **拉 episode 上下文**——节目页面常含嘉宾名、专有名词的标准写法：
   ```bash
   curl -sL https://r.jina.ai/<原始 URL>
   ```
   `r.jina.ai` 把任意页面渲染成 markdown，无需 key
3. **应用清洗策略**——见下文「baseline」+ 平台特化
4. **写入 sibling 文件**：`<原文件>.cleaned.txt`（也可同时输出 `.cleaned.srt`，按 segment 边界对齐），原 transcript **保持不动**

### Baseline 清洗规则（所有平台都适用）

修：
- 标点（ASR 经常少句号、逗号）
- 明显的人名 / 专有名词错字（用 episode 上下文里出现过的标准写法对齐）
- 重复词 / 口癖（"那个那个"、"嗯嗯啊"）
- 同一句被切成两个 segment 的合并

不动：
- 改写措辞、整段删减、总结、增加内容
- 段落顺序

### 不同平台的策略不同

baseline 之上每个平台/内容类型有特化规则，**写在 `domain-skills/<平台>.md` 的"清洗要点"小节**。例如：

- 中文播客：术语英汉混杂时怎么处理（直接保留 / 翻译 / 加括注）
- 技术访谈：代码相关词术 ASR 经常错（"k8s" 听成"K 8 S"等），要建小词典
- 教学/演讲：可能要加入主题分段标记

撞到 baseline 不够用的内容类型，**把规则写进对应的 `domain-skills/<平台>.md`**，下次该平台的 transcript 就有据可依。

## 起步前的环境

- `uv sync` 装依赖
- 本地转录：`uv tool install mlx-whisper`（仅 Apple Silicon）
- 远端转录任选其一：`export ELEVENLABS_API_KEY=...` / `export GROQ_API_KEY=...`

## 撞到没覆盖的情况怎么办

1. 改 `helpers.py` / `sources.py` / `audio.py` 加新分支
2. 把学到的怪癖落到 `domain-skills/<平台>.md` 或 `interaction-skills/<机制>.md`
3. 不要写"今天我做了 ABC"流水账；写**下次撞到同样问题的 agent 一眼能用的事实**——稳定的 selector、URL 模式、API 形状、为什么需要这个 wait
