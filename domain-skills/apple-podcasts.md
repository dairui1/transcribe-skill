# Apple Podcasts (podcasts.apple.com)

URL 形如 `https://podcasts.apple.com/<lang>/podcast/<slug>/id<collectionId>?i=<trackId>`。
- `collectionId`：节目 ID（必有）
- `trackId`（query `i`）：单期 ID（点开某期才有；只到节目首页就没有）

## 拿 audio URL 的稳定路径

不抓页面——用 iTunes Lookup API（无需 key）：

```
GET https://itunes.apple.com/lookup?id=<collectionId>&entity=podcastEpisode&limit=30
Accept: application/json
```

返回 `results: [...]`，里面有：
- `wrapperType: "podcastEpisode"` 的项 → 单期，`episodeUrl` 是 audio 直链
- `kind: "podcast"` 的项 → 节目元数据，含 `feedUrl`（RSS）

匹配 `trackId` 找具体期；没 `trackId` 就取 results 中第一条 `podcastEpisode`。

## RSS fallback

iTunes Lookup 限制只返回最近 30 期。要老期：从 `feedUrl` 拉 RSS XML，找 `<enclosure url="...">`。

## 已知陷阱

- iTunes API 是历史接口，文档稀少但很稳定，没 rate limit 公示
- `episodeUrl` 通常 redirect 一次到 CDN
- 中文节目 `<lang>` 段可能是 `cn` 或 `us`，不影响 lookup
