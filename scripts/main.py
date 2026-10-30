import json
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import config
from scripts.fetcher import fetch_all, load_history, save_history
from scripts.analyzer import analyze_news, analyze_boards
from scripts.renderer import build_render_context, render


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


def main():
    today = datetime.now(ZoneInfo("Asia/Shanghai"))
    today_str = today.strftime("%Y-%m-%d")
    print(f"[INFO] Running pipeline for {today_str}")

    sources = json.loads(config.SOURCES_PATH.read_text(encoding="utf-8"))

    # ---- Step 1: 抓取 ----
    raw_news = fetch_all(sources)
    total = sum(len(v) for v in raw_news.values())
    print(f"[INFO] Total new items across boards: {total}")

    if total == 0:
        print("[INFO] No new items today. Refreshing page with previous analysis if exists.")
        state = load_board_state()
        if state.get("last_render"):
            config.DIST_DIR.mkdir(exist_ok=True)
            (config.DIST_DIR / "index.html").write_text(state["last_render"], encoding="utf-8")
        return

    # ---- Step 2: 结构化资讯 ----
    structured = analyze_news(raw_news, today_str)
    print(f"[INFO] Structured news: {sum(len(v) for v in structured.get('news', {}).values())} items")

    # ---- Step 3: 回填 published 字段 ----
    url_to_pub = {}
    for board_items in raw_news.values():
        for item in board_items:
            url_to_pub[item["url"]] = item["published"]
    for board_id, items in structured.get("news", {}).items():
        for item in items:
            item["published"] = url_to_pub.get(item.get("url", ""), today.isoformat())

    # ---- Step 4: 板块深度解析 ----
    state = load_board_state()
    history = state.get("history", [])
    board_analysis = analyze_boards(structured, history, today_str)

    # ---- Step 5: 渲染 ----
    ctx = build_render_context(sources, structured, board_analysis, today)
    html = render(ctx)
    config.DIST_DIR.mkdir(exist_ok=True)
    (config.DIST_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"[INFO] Rendered dist/index.html ({len(html)} bytes)")

    # ---- Step 6: 更新历史 ----
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