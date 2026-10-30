import json
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from scripts.config import TEMPLATE_PATH, BOARD_ORDER, LINKAGE_CHAIN, LINKAGE_RELATIONS


def _split_date(iso_str: str) -> tuple:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%m.%d"), str(dt.year)
    except Exception:
        now = datetime.now()
        return now.strftime("%m.%d"), str(now.year)


def build_render_context(
    sources: dict,
    structured_news: dict,
    board_analysis: dict,
    today: datetime,
) -> dict:
    boards = []
    for board_id in BOARD_ORDER:
        cfg = sources[board_id]
        analysis = board_analysis.get("boards", {}).get(board_id, {})
        news_items = structured_news.get("news", {}).get(board_id, []) or []

        news_render = []
        for i, item in enumerate(news_items):
            date_short, year = _split_date(item.get("published", ""))
            news_render.append({
                "date_short": date_short,
                "year": year,
                "tag": item.get("tag", ""),
                "is_new": i < 3,
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "sources": [{
                    "name": item.get("source", "来源"),
                    "url": item.get("url", "#"),
                    "desc": item.get("title", ""),
                }],
            })

        boards.append({
            "id": board_id,
            "name": cfg["name"],
            "color": cfg["color"],
            "color_dark": cfg.get("color_dark", cfg["color"]),
            "status": analysis.get("status", "—"),
            "news": news_render,
            "analysis": analysis.get("analysis", []),
            "outlook": analysis.get("outlook", []),
        })

    board_name = {b["id"]: b["name"] for b in boards}
    board_color = {b["id"]: b["color"] for b in boards}
    board_color_dark = {b["id"]: b["color_dark"] for b in boards}

    linkage_relations = []
    for rel in LINKAGE_RELATIONS:
        linkage_relations.append({
            "from_name": board_name.get(rel["from"], rel["from"]),
            "to_names": [board_name.get(t, t) for t in rel["to"]],
            "color": board_color.get(rel["from"], "#9c2b22"),
            "color_dark": board_color_dark.get(rel["from"], "#e5897a"),
            "text": rel["text"],
        })

    weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][today.weekday()]

    return {
        "date_cn": f"{today.year} 年 {today.month} 月 {today.day} 日　星期{weekday_cn}",
        "date_iso": today.strftime("%Y-%m-%d"),
        "lede": board_analysis.get("lede", ""),
        "boards": boards,
        "chain": [{
            "id": b["id"],
            "name": b["name"],
            "color": b["color"],
            "color_dark": b["color_dark"],
        } for b in boards],
        "relations": linkage_relations,
        "linkage_conclusion": board_analysis.get("linkage_conclusion", ""),
        "summary_items": board_analysis.get("summary", []),
    }


def render(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_PATH.parent)), autoescape=False)
    template = env.get_template(TEMPLATE_PATH.name)
    return template.render(**context)