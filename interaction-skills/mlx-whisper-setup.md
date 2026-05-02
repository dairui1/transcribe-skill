# mlx-whisper 本地引擎

Apple Silicon 专属，免费、离线、隐私好。但环境是这个 skill 唯一**真有坑**的地方。

## 安装

```bash
uv tool install mlx-whisper
brew install ffmpeg
```

`uv tool install` 会建独立 venv，可执行文件 symlink 到 `~/.local/bin/mlx_whisper`。`uv tool` 不冲突 pyproject 依赖——保持 helpers.py 干净。

## 检查可用

```bash
mlx_whisper --help                 # 应该输出 usage
ffmpeg -version | head -1          # 任何最近 5 年的版本都行
```

## 第一次运行：模型下载

`mlx_whisper` 默认用 `mlx-community/whisper-large-v3-turbo`，第一次跑会从 HuggingFace 下载 ~1.5GB 到 `~/.cache/huggingface/hub/`。**没进度条**，看起来像挂了，等 5-10 分钟。

显式指定 model：`mlx_whisper audio.m4a --model mlx-community/whisper-large-v3-mlx`。可选 model：

| model | 大小 | 速度 | 适用 |
|---|---|---|---|
| `mlx-community/whisper-tiny-mlx` | 75MB | 极快 | 噪音多、内容短 |
| `mlx-community/whisper-large-v3-turbo` | 1.5GB | 中（默认） | 大多数情况 |
| `mlx-community/whisper-large-v3-mlx` | 3GB | 慢 | 多语言混杂、专业术语多 |

## 输出文件位置

`mlx_whisper audio.m4a --output-dir <dir> --output-format all` 在 `<dir>` 生成：
- `<basename>.txt` — 纯文本
- `<basename>.srt` — 字幕
- `<basename>.json` — segments + metadata
- `<basename>.vtt` — WebVTT
- `<basename>.tsv` — segment 表格

`_transcribe_mlx` 用了一个隐藏目录 `.<stem>.mlx/` 避免污染源音频目录。

## 语言提示

模型自动检测，但**短音频或多语言混杂时会猜错**（粤语经常被识别为日语）。已知语言时显式传 `language="zh"`/`"en"`/`"ja"`，准确率明显提升。

## 已知陷阱

- **`mlx_whisper` 命令名带下划线，不是连字符**——`mlx-whisper` 是 PyPI 包名，CLI 是 `mlx_whisper`
- **必须 Apple Silicon**——M1/M2/M3/M4。Intel Mac 装不上 mlx
- **ffmpeg 必须在 PATH**——mlx_whisper 内部用 ffmpeg 解码非 wav 输入。`brew install ffmpeg` 即可
- **首次 dispatch 慢**——MLX 框架有 JIT 编译，第一次调用慢 30 秒以上，之后正常
- **不要并发跑多个 mlx_whisper 进程**——共享 GPU，并发会互相拖累。串行处理 chunk

## 与远端引擎的取舍

| 维度 | mlx-whisper | ElevenLabs | Groq |
|---|---|---|---|
| 价格 | 免费 | $0.40/小时 | $0.04/小时 |
| 速度 | 1x 实时 | ~5x | ~50x |
| 质量 | 好 | 最好 | 中（偶尔幻觉） |
| 离线 | ✅ | ❌ | ❌ |
| 隐私 | ✅ | ❌ | ❌ |
| 中文 | 好 | 好 | 中 |

默认 mlx-whisper；要快用 Groq；要最高质量 + 说话人分离用 ElevenLabs。
