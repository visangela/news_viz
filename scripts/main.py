import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scripts import config
from scripts.fetcher import fetch_all, load_history, save_history
from scripts.analyzer import analyze_news, analyze_boards
from scripts.renderer import (
    build_render_context, render,
    build_archive_context, render_archive,
)


def load_board_state() -> dict:
    if config.BOARD_STATE_PATH.exists():
        try:
            return json.loads(config.BOARD_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"history": []}
    return {"history": []}


def save_board_state(state: dict) -> None:
    state["history"] = state["history"][-config.BOARD_STATE_RETENTION_DAYS:]
    config.BOARD_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_archive() -> dict:
    if config.ARCHIVE_PATH.exists():
        try:
            data = json.loads(config.ARCHIVE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "by_date" in data:
                return data
        except Exception:
            pass
    return {"by_date": {}}


def save_archive(archive: dict) -> None:
    cutoff = (datetime.now() - timedelta(days=config.ARCHIVE_RETENTION_DAYS)).strftime("%Y-%m-%d")
    by_date = archive.get("by_date", {})
    by_date = {d: v for d, v in by_date.items() if d >= cutoff}
    archive["by_date"] = by_date
    config.ARCHIVE_PATH.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _render_archive_page(sources: dict, today: datetime) -> None:
    archive = load_archive()
    ctx = build_archive_context(sources, archive, today)
    html = render_archive(ctx)
    config.DIST_DIR.mkdir(exist_ok=True)
    (config.DIST_DIR / "archive.html").write_text(html, encoding="utf-8")
    print(f"[INFO] Rendered dist/archive.html ({len(html)} bytes, {ctx['total_entries']} entries)")


def main():
    today = datetime.now(ZoneInfo("Asia/Shanghai"))
    today_str = today.strftime("%Y-%m-%d")
    print(f"[INFO] Running pipeline for {today_str}")

    sources = json.loads(config.SOURCES_PATH.read_text(encoding="utf-8"))

    raw_news = fetch_all(sources)
    total = sum(len(v) for v in raw_news.values())
    print(f"[INFO] Total new items across boards: {total}")

    if total == 0:
        print("[INFO] No new items today. Refreshing existing pages if any.")
        state = load_board_state()
        if state.get("last_render"):
            config.DIST_DIR.mkdir(exist_ok=True)
            (config.DIST_DIR / "index.html").write_text(state["last_render"], encoding="utf-8")
        _render_archive_page(sources, today)
        return

    structured = analyze_news(raw_news, today_str)
    print(f"[INFO] Structured news: {sum(len(v) for v in structured.get('news', {}).values())} items")

    url_to_pub = {}
    for board_items in raw_news.values():
        for item in board_items:
            url_to_pub[item["url"]] = item["published"]
    for board_id, items in structured.get("news", {}).items():
        for item in items:
            item["published"] = url_to_pub.get(item.get("url", ""), today.isoformat())

    state = load_board_state()
    history = state.get("history", [])
    board_analysis = analyze_boards(structured, history, today_str)

    # ---- 渲染首页 ----
    ctx = build_render_context(sources, structured, board_analysis, today)
    html = render(ctx)
    config.DIST_DIR.mkdir(exist_ok=True)
    (config.DIST_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"[INFO] Rendered dist/index.html ({len(html)} bytes)")

    # ---- 写入归档数据 ----
    archive = load_archive()
    entries_by_board = {}
    for board_id, items in structured.get("news", {}).items():
        if not items:
            continue
        entries_by_board[board_id] = [{
            "title": it.get("title", ""),
            "tag": it.get("tag", ""),
            "url": it.get("url", ""),
            "source": it.get("source", ""),
        } for it in items]
    if entries_by_board:
        archive.setdefault("by_date", {})[today_str] = entries_by_board
        save_archive(archive)
        added = sum(len(v) for v in entries_by_board.values())
        print(f"[INFO] Archive updated: +{added} entries for {today_str}")

    # ---- 渲染归档页 ----
    _render_archive_page(sources, today)

    # ---- 更新历史 ----
    hist = load_history()
    for board_items in raw_news.values():
        for item in board_items:
            hist[item["url"]] = today_str
    save_history(hist)

    today_board_summary = {}
    for board_id, a in board_analysis.get("boards", {}).items():
        today_board_summary[board_id] = {
            "status": a.get("status", ""),
            "analysis_short": (a.get("analysis", [""])[0] or "")[:200],
        }
    history.append({"date": today_str, "boards": today_board_summary})
    state["history"] = history
    state["last_render"] = html
    save_board_state(state)
    print("[INFO] Pipeline complete.")


if __name__ == "__main__":
    main()