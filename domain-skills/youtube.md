# YouTube (youtube.com / youtu.be)

**不要写 YouTube 特化 resolver**——`yt-dlp` 已经覆盖。`sources.resolve` 对未知 host 会先试 `_generic`，失败 fallback 到 `_ytdlp`，YouTube 走的就是这条。

## 关键事实

- yt-dlp 有 1500+ extractor，YouTube 是头号一等公民，更新最勤
- 调用形式：`yt-dlp -j --no-warnings -f bestaudio <url>` 拿 JSON 元数据，里面 `url` 字段就是音频直链
- 鉴权：直链含 `signature` 和 `expire` 参数，**几小时后就失效**——拿到立即下载，不要存库
- 取到的 `url` 通常是 `.m4a` 或 `.webm`（Opus），mlx-whisper / ElevenLabs / Groq 都吃

## yt-dlp 一并覆盖的视频站

不需要为这些写特化：

- B 站 (bilibili.com)
- 推特 / X 视频
- TikTok / Instagram Reels
- Vimeo / Dailymotion
- 各种新闻站内嵌视频

完整清单：`yt-dlp --list-extractors`

## 例外（撞到再处理）

- **"Sign in to confirm you're not a bot" 反爬**：YouTube 现在频繁触发。`sources._ytdlp` 已实现自动 retry——首次失败且 stderr 含此字样或 `cookies` 时，重试时带 `--cookies-from-browser <浏览器>`。浏览器名走环境变量 `YTDLP_COOKIES_BROWSER`，默认 `chrome`。前提是浏览器里登录了 YouTube
- **会员限定 / 私享视频**：同样靠 `--cookies-from-browser` 拿到登录态后才能下
- **直播流**：yt-dlp 能下，但要等结束或带 `--live-from-start`
- **被墙的内容**：yt-dlp 错误信息会明示，让用户换网络
- **超长视频（3 小时+）**：bestaudio 文件可能 200MB+，下载慢；考虑 `-f worstaudio` 给 ASR 用够了

## 维持 yt-dlp 新鲜

YouTube 反爬变化快，旧版 yt-dlp 经常突然失效。撞到 "Unable to extract" 报错先试：

```bash
uv tool upgrade yt-dlp
# 或
brew upgrade yt-dlp
```
