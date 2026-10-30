import json
import re
from datetime import datetime, timedelta, timezone

import feedparser

from scripts.config import (
    FETCH_WINDOW_HOURS, MAX_NEWS_PER_BOARD,
    HISTORY_RETENTION_DAYS, NEWS_HISTORY_PATH,
)


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


def fetch_board_news(board_id: str, board_cfg: dict, since_dt: datetime, history: dict) -> list:
    news_list = []
    for feed_cfg in board_cfg.get("feeds", []):
        try:
            feed = feedparser.parse(feed_cfg["url"])
        except Exception as e:
            print(f"[WARN] Feed parse failed: {feed_cfg['name']} ({e})")
            continue

        for entry in feed.entries[:50]:
            url = entry.get("link", "").strip()
            if not url or url in history:
                continue

            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
            if not title:
                continue

            text_to_check = title + " " + summary
            if not match_keywords(text_to_check, board_cfg.get("keywords", [])):
                continue

            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                dt = datetime(*published[:6], tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            if dt < since_dt:
                continue

            news_list.append({
                "title": title,
                "summary": summary[:600],
                "url": url,
                "source": feed_cfg["name"],
                "published": dt.isoformat(),
            })

    # 去重（同一 URL 可能出现在多个 feed）
    seen = set()
    unique = []
    for item in news_list:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        unique.append(item)

    unique.sort(key=lambda x: x["published"], reverse=True)
    return unique[:MAX_NEWS_PER_BOARD]


def fetch_all(sources: dict) -> dict:
    history = load_history()
    since_dt = datetime.now(timezone.utc) - timedelta(hours=FETCH_WINDOW_HOURS)
    result = {}
    for board_id, board_cfg in sources.items():
        items = fetch_board_news(board_id, board_cfg, since_dt, history)
        result[board_id] = items
        print(f"[INFO] {board_id}: fetched {len(items)} new items")
    return result