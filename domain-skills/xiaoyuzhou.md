# 小宇宙 (xiaoyuzhoufm.com)

URL 形如 `https://www.xiaoyuzhoufm.com/episode/<eid>`，其中 `<eid>` 是字母数字。

## 拿 audio URL 的稳定路径

`__NEXT_DATA__` JSON（页面里的 `<script id="__NEXT_DATA__" type="application/json">`），里面 `props.pageProps.episode.enclosure.url`。

如果 `episode` 不在 `pageProps` 顶层，遍历 `pageProps.dehydratedState.queries[].state.data.episode`——SSR 缓存的 React Query 状态。

备用：HTML head 的 `<meta property="og:audio" content="...">`，命中率不到 100% 但偶尔 `__NEXT_DATA__` 取空时能救场。

## 必备 header

- `User-Agent`：用真实浏览器 UA，否则可能拿到风控页
- `Referer: https://www.xiaoyuzhoufm.com/`：偶尔能避免被识别为爬虫

## episode_id 推导

优先 `episode.eid`，再 `episode.id`，都没有就从 URL `/episode/<eid>` 正则取。

## 已知陷阱

- audio URL 是 CDN 直链（`media.xyzcdn.net/...`），有时间戳鉴权但常驻几天；不要缓存太久
