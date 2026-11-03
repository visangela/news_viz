import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from scripts.config import (
    FETCH_WINDOW_HOURS, MAX_NEWS_PER_BOARD,
    HISTORY_RETENTION_DAYS, NEWS_HISTORY_PATH,
    HTML_FETCH_TIMEOUT, DEFAULT_UA,
)

# 板块级覆盖：短剧赛事/扶持类信息间隔长，给更大窗口
BOARD_FETCH_WINDOW_OVERRIDE = {
    "drama": 72,
}
BOARD_MAX_NEWS_OVERRIDE = {
    "drama": 15,
}


def clean_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def match_keywords(text: str, keywords: list) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def load_history() -> dict:
    if NEWS_HISTORY_PATH.exists():
        try:
            return json.loads(NEWS_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_history(history: dict) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)).strftime("%Y-%m-%d")
    pruned = {url: d for url, d in history.items() if d >= cutoff}
    NEWS_HISTORY_PATH.write_text(json.dumps(pruned, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- RSS 抓取 ----------------

def fetch_rss_feed(feed_cfg: dict, since_dt: datetime, history: dict) -> list:
    try:
        feed = feedparser.parse(feed_cfg["url"])
    except Exception as e:
        print(f"[WARN] RSS parse failed: {feed_cfg['name']} ({e})")
        return []

    items = []
    for entry in feed.entries[:50]:
        url = entry.get("link", "").strip()
        if not url or url in history:
            continue

        title = clean_text(entry.get("title", ""))
        summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
        if not title:
            continue

        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            dt = datetime(*published[:6], tzinfo=timezone.utc)
        else:
            dt = datetime.now(timezone.utc)

        if dt < since_dt:
            continue

        items.append({
            "title": title,
            "summary": summary[:600],
            "url": url,
            "source": feed_cfg["name"],
            "published": dt.isoformat(),
        })
    return items


# ---------------- HTML 列表页抓取 ----------------

def _is_valid_title(title: str, hints: dict) -> bool:
    title_min = hints.get("title_min_length", 8)
    title_max = hints.get("title_max_length", 90)
    if len(title) < title_min or len(title) > title_max:
        return False
    # 排除纯数字、纯符号、纯标点
    if not re.search(r"[\u4e00-\u9fa5A-Za-z]", title):
        return False
    # 排除明显导航词
    nav_words = ["首页", "登录", "注册", "更多", "下一页", "上一页", "返回", "关于我们", "联系方式", "隐私政策", "用户协议"]
    if title in nav_words:
        return False
    return True


def fetch_html_listing(feed_cfg: dict, since_dt: datetime, history: dict) -> list:
    url = feed_cfg["url"]
    hints = feed_cfg.get("hints", {})
    headers = {"User-Agent": hints.get("user_agent", DEFAULT_UA)}

    try:
        resp = requests.get(url, headers=headers, timeout=HTML_FETCH_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] HTML fetch failed: {feed_cfg['name']} {url} ({e})")
        return []

    if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "ascii"):
        # resp.encoding = resp.apparent_encoding or "utf-8"
        ct = resp.headers.get("Content-Type", "")
        if "charset=" in ct:
            resp.encoding = ct.split("charset=")[-1].split(";")[0].strip()
        else:
            resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")

    selector = hints.get("selector", "a")
    href_must = hints.get("href_must_contain", [])
    href_exclude = hints.get(
        "exclude_href_patterns",
        ["#", "javascript:", "mailto:", "/tag/", "/category/", "/login", "/register", "/user/"],
    )
    max_items = hints.get("max_items", 30)

    items = []
    seen_urls = set()
    now_iso = datetime.now(timezone.utc).isoformat()

    for a in soup.select(selector):
        href = (a.get("href") or "").strip()
        title = a.get_text(strip=True)

        if not href or not title:
            continue
        if not _is_valid_title(title, hints):
            continue
        if any(p in href for p in href_exclude):
            continue
        if href_must and not any(p in href for p in href_must):
            continue

        full_url = urljoin(url, href)
        if not full_url.startswith("http"):
            continue
        parsed = urlparse(full_url)
        if not parsed.netloc:
            continue

        if full_url in seen_urls or full_url in history:
            continue
        seen_urls.add(full_url)

        items.append({
            "title": title,
            "summary": "",
            "url": full_url,
            "source": feed_cfg["name"],
            "published": now_iso,
        })
        if len(items) >= max_items:
            break

    print(f"[INFO] HTML listing {feed_cfg['name']}: parsed {len(items)} candidate links")
    return items


# ---------------- 板块抓取 ----------------

def fetch_board_news(board_id: str, board_cfg: dict, history: dict) -> list:
    window_hours = BOARD_FETCH_WINDOW_OVERRIDE.get(board_id, FETCH_WINDOW_HOURS)
    max_items = BOARD_MAX_NEWS_OVERRIDE.get(board_id, MAX_NEWS_PER_BOARD)
    since_dt = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    news_list = []
    for feed_cfg in board_cfg.get("feeds", []):
        feed_type = feed_cfg.get("type", "rss")
        if feed_type == "html":
            entries = fetch_html_listing(feed_cfg, since_dt, history)
        else:
            entries = fetch_rss_feed(feed_cfg, since_dt, history)

        for item in entries:
            if not match_keywords(item["title"] + " " + item["summary"], board_cfg.get("keywords", [])):
                continue
            news_list.append(item)

    # 去重
    seen = set()
    unique = []
    for item in news_list:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        unique.append(item)

    unique.sort(key=lambda x: x["published"], reverse=True)
    return unique[:max_items]


def fetch_all(sources: dict) -> dict:
    history = load_history()
    result = {}
    for board_id, board_cfg in sources.items():
        items = fetch_board_news(board_id, board_cfg, history)
        result[board_id] = items
        print(f"[INFO] {board_id}: fetched {len(items)} new items")
    return result