"""
Source resolvers — URL 到音频直链的平台特化逻辑。

入口是 resolve()。它按域名分发到平台特化函数，未知域名 fallback 到
generic 嗅探，再失败 fallback 到 yt-dlp。

撞到没覆盖的平台或现有平台改了 selector → 直接改这个文件，
并把"为什么这样找"写进 domain-skills/<平台>.md。
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)
HTML_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "User-Agent": UA,
}


@dataclass
class Source:
    audio_url: str
    title: str = ""
    source: str = ""
    episode_id: str = ""
    meta: dict = field(default_factory=dict)


def resolve(url: str) -> Source:
    """主分发函数。"""
    host = urlparse(url).hostname or ""

    if host == "www.xiaoyuzhoufm.com" and "/episode/" in url:
        return _xiaoyuzhou(url)
    if host == "podcasts.apple.com":
        return _apple_podcasts(url)
    if host == "open.spotify.com" and "/episode/" in url:
        raise ValueError(
            "Spotify 节目受 DRM 保护无法直接下载。请改用 Apple Podcasts 链接、"
            "RSS 链接，或同一节目的其他平台来源。"
        )

    # 未知域名先试 generic（HTML 嗅探），失败再 fallback 到 yt-dlp
    try:
        return _generic(url)
    except Exception:
        return _ytdlp(url)


# --------------------------------------------------------------------------- #
# 小宇宙
# --------------------------------------------------------------------------- #

def _xiaoyuzhou(url: str) -> Source:
    """
    小宇宙 audio URL 藏在 __NEXT_DATA__ 的 pageProps.episode.enclosure.url。
    备用：og:audio meta。
    """
    html = _fetch_html(url, extra={"Referer": "https://www.xiaoyuzhoufm.com/"})

    audio_url = title = ""
    eid = ""
    m = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>([\s\S]*?)</script>',
        html,
        re.I,
    )
    if m:
        data = json.loads(m.group(1))
        ep = (data.get("props", {}).get("pageProps", {}) or {}).get("episode") or {}
        if not ep:
            for q in (data.get("props", {}).get("pageProps", {}) or {}).get("dehydratedState", {}).get("queries", []):
                cand = (q.get("state", {}).get("data", {}) or {}).get("episode")
                if cand:
                    ep = cand
                    break
        audio_url = (ep.get("enclosure") or {}).get("url") or ((ep.get("media") or {}).get("source") or {}).get("url") or ""
        title = ep.get("title", "")
        eid = ep.get("eid") or ep.get("id") or ""

    if not audio_url:
        og = re.search(r'<meta[^>]*property="og:audio"[^>]*content="([^"]+)"', html, re.I)
        if og:
            audio_url = og.group(1)

    if not audio_url:
        raise RuntimeError("小宇宙页面里找不到 audio URL")

    if not eid:
        m = re.search(r"/episode/([A-Za-z0-9]+)", url)
        eid = m.group(1) if m else ""

    return Source(audio_url=audio_url, title=title, source="xiaoyuzhou", episode_id=eid)


# --------------------------------------------------------------------------- #
# Apple Podcasts
# --------------------------------------------------------------------------- #

_APPLE_PATH = re.compile(r"^/[a-z]{2}/podcast/[^/]+/id(\d+)")


def _apple_podcasts(url: str) -> Source:
    """
    Apple Podcasts 用 iTunes Lookup API 拿 episode 元数据。
    URL 形如 /<lang>/podcast/<slug>/id<collectionId>?i=<trackId>。
    集合 audio 在 entry.episodeUrl；找不到时 fallback 到 RSS feed。
    """
    parsed = urlparse(url)
    pm = _APPLE_PATH.match(parsed.path)
    if not pm:
        raise ValueError("不是 Apple Podcasts episode URL")
    collection_id = pm.group(1)
    track_id = ""
    for kv in (parsed.query or "").split("&"):
        if kv.startswith("i="):
            track_id = kv[2:]
            break

    api = f"https://itunes.apple.com/lookup?id={collection_id}&entity=podcastEpisode&limit=30"
    r = httpx.get(api, headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    results = r.json().get("results", [])

    if not track_id:
        ep = next((e for e in results if e.get("wrapperType") == "podcastEpisode" and e.get("episodeUrl")), None)
    else:
        ep = next(
            (e for e in results if e.get("wrapperType") == "podcastEpisode" and str(e.get("trackId")) == track_id),
            None,
        )

    if ep and ep.get("episodeUrl"):
        return Source(
            audio_url=ep["episodeUrl"],
            title=ep.get("trackName", ""),
            source="apple-podcasts",
            episode_id=str(ep.get("trackId", "")),
        )

    # Fallback: 节目 RSS feed 第一条 enclosure
    show = next((e for e in results if e.get("kind") == "podcast" and e.get("feedUrl")), None)
    if not show:
        raise RuntimeError("iTunes lookup 没返回 RSS feed")
    feed = httpx.get(show["feedUrl"], headers={"Accept": "application/rss+xml,application/xml,text/xml"}, timeout=30)
    feed.raise_for_status()
    enc = re.search(r'<enclosure[^>]*url=["\']([^"\']+)["\']', feed.text, re.I)
    if not enc:
        raise RuntimeError("RSS feed 里找不到 enclosure")
    return Source(audio_url=enc.group(1), source="apple-podcasts", episode_id=track_id or collection_id)


# --------------------------------------------------------------------------- #
# Generic（任意 HTML 页面嗅探）
# --------------------------------------------------------------------------- #

_AUDIO_EXT = re.compile(r"\.(aac|flac|m4a|mp3|oga|ogg|opus|wav)(?:$|[?#&])", re.I)


def _generic(url: str) -> Source:
    """
    通用嗅探。两条主路径：
      1. URL 已经是直链音频 → HEAD 验证后直接返回
      2. HTML 页面 → 找 og:audio meta → 找 RSS feed link → 解析 enclosure
    更复杂的（JSON-LD audio object、<audio>/<source> 标签）边角时由 agent 加进来。
    """
    if _AUDIO_EXT.search(url):
        return Source(audio_url=url, source=urlparse(url).hostname or "direct")

    html = _fetch_html(url)

    og = re.search(r'<meta[^>]*property="og:audio"[^>]*content="([^"]+)"', html, re.I)
    if og:
        title = _extract_title(html)
        return Source(audio_url=og.group(1), title=title, source=urlparse(url).hostname or "")

    # RSS feed link
    feeds = re.findall(
        r'<link[^>]*rel=["\']alternate["\'][^>]*type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    for feed_href in feeds:
        feed_url = feed_href if feed_href.startswith("http") else _join(url, feed_href)
        try:
            feed_xml = httpx.get(feed_url, headers={"Accept": "application/rss+xml,application/xml"}, timeout=30).text
        except Exception:
            continue
        enc = re.search(r'<enclosure[^>]*url=["\']([^"\']+)["\']', feed_xml, re.I)
        if enc:
            return Source(audio_url=enc.group(1), title=_extract_title(html), source=urlparse(url).hostname or "")

    raise RuntimeError("generic 嗅探失败：og:audio 和 RSS enclosure 都没找到")


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    return m.group(1).strip() if m else ""


def _join(base: str, href: str) -> str:
    from urllib.parse import urljoin
    return urljoin(base, href)


# --------------------------------------------------------------------------- #
# yt-dlp 兜底
# --------------------------------------------------------------------------- #

def _ytdlp(url: str) -> Source:
    """yt-dlp 兜底——YouTube/B 站/绝大多数视频站都吃。"""
    out = subprocess.run(
        ["yt-dlp", "-j", "--no-warnings", "-f", "bestaudio", url],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(out.stdout)
    return Source(
        audio_url=info["url"],
        title=info.get("title", ""),
        source=info.get("extractor", "yt-dlp"),
        episode_id=info.get("id", ""),
        meta={"duration": info.get("duration"), "uploader": info.get("uploader")},
    )


# --------------------------------------------------------------------------- #
# 内部
# --------------------------------------------------------------------------- #

def _fetch_html(url: str, extra: dict | None = None) -> str:
    headers = {**HTML_HEADERS, **(extra or {})}
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    r.raise_for_status()
    return r.text
