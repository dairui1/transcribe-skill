# transcribe-skill

把任意视频/音频源（YouTube、播客、直链、本地文件）转录成文本与 SRT，并可选地用节目页面上下文清洗 ASR 结果。

遵循 [meta-skill](https://github.com/dairui1/meta-skill) 规范——薄、能自愈、技能能沉淀。

## 起步

```bash
git clone https://github.com/dairui1/transcribe-skill
cd transcribe-skill
uv sync

# 本地转录（仅 Apple Silicon）
uv tool install mlx-whisper
brew install yt-dlp ffmpeg

# 远端转录任选其一
export ELEVENLABS_API_KEY=...
export GROQ_API_KEY=...

# 清洗：不需要 key——agent 自己读 transcript 直接清，见 SKILL.md「清洗」节
```

## 怎么用

不要把它当 CLI 用——它是给 agent 的 skill。读 [SKILL.md](./SKILL.md) 就够了。

## 安装到 Claude Code（可选）

把下面这段贴进 Claude Code：

```
请把 https://github.com/dairui1/transcribe-skill 整个仓库 clone 到
~/.claude/skills/transcribe/，然后告诉我以后可以让你转录任意视频/音频。
```

之后说"帮我转录这个 URL"就会触发 skill。

## License

[MIT](./LICENSE)
