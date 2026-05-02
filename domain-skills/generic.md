# Generic（任意 HTML 页面嗅探）

未知域名的 fallback。当前 `sources._generic` 只覆盖两条主路径：

## 路径 1：URL 已经是直链音频

`*.mp3 / *.m4a / *.aac / *.flac / *.ogg / *.opus / *.wav`（含 query 时也认）。直接返回，不发 HTTP。

## 路径 2：HTML 页面

按以下顺序找 audio URL，第一个命中即返回：

1. `<meta property="og:audio" content="...">`——OpenGraph 标准，命中率最高
2. `<link rel="alternate" type="application/rss+xml" href="...">` 或 `application/atom+xml`，拉 feed 后找首个 `<enclosure url="...">`

## 没覆盖（撞到时再加）

按命中率从高到低，撞到再 self-heal 进 `sources._generic`：

1. **JSON-LD AudioObject**——`<script type="application/ld+json">` 里 `@type: AudioObject` 的 `contentUrl`。Substack、Medium 这类博客平台常见。
2. **`<audio>` 或 `<source>` 标签的 `src`**——少数手写站点
3. **og:url + RSS 嗅探**——og 里给的不是 audio 而是 episode canonical，要再走 RSS feed 一遍
4. **JS 渲染的 SPA**——og:audio 都没的话，要么上 playwright，要么放弃 generic 走 yt-dlp

## 头部

```
User-Agent: <真实 Chrome UA>
Accept: text/html,...
Accept-Language: en-US,en;q=0.9,zh-CN;q=0.8
```

少了 UA 一半的站点会返回风控页。

## 已知陷阱

- HTML 嗅出来的 audio URL 可能是相对路径，记得 `urljoin` 跟 base URL 拼回去
- RSS feed 的第一条 enclosure 不一定是用户想要的那期——节目主页 URL 解出来都是"最新一期"，要单期就需要 episode 页面 URL
