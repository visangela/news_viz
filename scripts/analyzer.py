import json
import os

from openai import OpenAI

from scripts.config import BOARD_ORDER

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

MODEL = "deepseek-chat"

# 与 data/sources.json 保持一致；增删板块时需同步更新
BOARD_NAMES = {
    "chip": "芯片与半导体",
    "memory": "存储",
    "llm": "AI 大模型",
    "agent": "AI 应用与 Agent",
    "hardware": "AI 硬件",
    "drama": "AI 短剧",
}

SYSTEM_PROMPT = (
    "你是「AI产业情报局」的资深产业分析师。"
    "你的任务是把零散的资讯整合成有判断力的产业分析，而不是简单拼凑新闻。"
    "输出必须是严格的 JSON 对象，不包含任何解释性文字、markdown 代码块标记或注释。"
    "重要：JSON 字符串值内部不要使用未转义的双引号，不要使用真实换行符（用空格代替），"
    "不要输出任何 JSON 之外的文字。"
)


def _safe_json_loads(content: str) -> dict:
    if not content or not content.strip():
        raise ValueError("LLM returned empty content")

    text = content.strip()

    # 去掉 markdown 代码块围栏
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 提取最外层 { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        ctx_start = max(0, e.pos - 100)
        ctx_end = min(len(text), e.pos + 100)
        print(f"[WARN] JSON decode error at pos {e.pos}: {e}")
        print(f"[WARN] Context: ...{text[ctx_start:ctx_end]}...")
        raise


def _call_llm_json(prompt: str, max_tokens: int = 3000, retries: int = 2) -> dict:
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.6 if attempt == 0 else 0.3,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content
            return _safe_json_loads(content)
        except Exception as e:
            last_err = e
            print(f"[WARN] LLM attempt {attempt + 1}/{retries + 1} failed: {e}")
            if attempt >= retries:
                raise
    raise last_err


# ---------------- 结构化资讯 ----------------

NEWS_STRUCT_PROMPT = """今天是 {today}。以下是今天各板块抓取到的原始资讯（JSON）：

{news_json}

请为每一条资讯生成结构化版本，要求：
- 保留原文 URL 和 source
- title 精简到 12-25 字，突出最关键的产业信息
- summary 80-150 字，说明"发生了什么"和"为什么重要"
- tag 3-6 字，概括这条资讯的产业维度（如"散热材料""财报""开源""平台治理"）
- 如果一条资讯涉及“创作大赛”“创投季”“激励计划”“扶持计划”“征集”，tag 优先使用“赛事”或“扶持”，不要用泛化的“动态”。

严格输出如下 JSON（不要任何其他字段）：
{{
  "news": {{
    "{first_board}": [
      {{"title": "...", "summary": "...", "tag": "...", "url": "...", "source": "..."}}
    ]
  }}
}}

注意：只对实际传入的板块输出；如果某个板块今日无资讯，则输出空数组。
字符串值内部不要使用未转义的双引号，不要使用真实换行符。"""


def analyze_news(raw_news: dict, today_str: str) -> dict:
    news_json = json.dumps(raw_news, ensure_ascii=False, indent=2)
    prompt = NEWS_STRUCT_PROMPT.format(
        today=today_str,
        news_json=news_json,
        first_board=BOARD_ORDER[0],
    )
    return _call_llm_json(prompt, max_tokens=5000)


# ---------------- 单板块分析 ----------------

BOARD_ANALYSIS_PROMPT = """今天是 {today}。你是 AI 产业分析师。以下是「{board_name}」板块今日的结构化资讯：

{news_json}

该板块过去 7 天的判断摘要（供判断延续或转折）：

{history_summary}

请输出该板块的深度解析，严格 JSON：
{{
  "status": "4-6字的板块状态标签",
  "analysis": [
    "第一段：今日最值得注意的信号、为什么重要、背后的产业结构性含义（100-180字）",
    "第二段：与近期趋势对比，是延续还是转折，涉及哪些产业链博弈（100-180字）"
  ],
  "outlook": [
    "中期（2027年前）走向判断（100-180字）",
    "长期（2028年后）走向判断（100-180字）"
  ]
}}

不要复述新闻，要有判断。
字符串值内部不要使用未转义的双引号，不要使用真实换行符。"""


def _analyze_single_board(board_id, news_items, history_summary, today_str):
    board_name = BOARD_NAMES.get(board_id, board_id)

    if not news_items:
        return {
            "status": "今日无新增",
            "analysis": [f"{board_name}板块今日暂无重要新资讯。持续关注后续动向，暂不做新的方向性判断。"],
            "outlook": ["暂无足够新信息支撑趋势更新，维持此前观察。"],
        }

    prompt = BOARD_ANALYSIS_PROMPT.format(
        today=today_str,
        board_name=board_name,
        news_json=json.dumps(news_items, ensure_ascii=False, indent=2),
        history_summary=history_summary,
    )
    return _call_llm_json(prompt, max_tokens=2500)


# ---------------- 全局总结 ----------------

GLOBAL_SUMMARY_PROMPT = """今天是 {today}。你是 AI 产业分析师。以下是今日六大板块的新闻标题与板块状态：

{global_ctx}

请输出全局判断，严格 JSON：
{{
  "lede": "一句话判断（150-250字），串联至少3个板块的共同信号",
  "linkage_conclusion": "共同矛盾分析（150-250字）",
  "summary": [
    {{"title": "总结标题", "body": "总结正文100-200字"}}
  ]
}}

summary 输出 6-7 条，覆盖主要板块和关键判断。
字符串值内部不要使用未转义的双引号，不要使用真实换行符。"""


def _analyze_global(structured_news, board_analysis_map, today_str):
    global_ctx = {}
    for board_id in BOARD_ORDER:
        items = structured_news.get("news", {}).get(board_id, []) or []
        ba = board_analysis_map.get(board_id, {})
        global_ctx[board_id] = {
            "name": BOARD_NAMES.get(board_id, board_id),
            "status": ba.get("status", ""),
            "news_titles": [{"title": it.get("title", ""), "tag": it.get("tag", "")} for it in items[:5]],
            "analysis_short": (ba.get("analysis", [""])[0] or "")[:160],
        }

    prompt = GLOBAL_SUMMARY_PROMPT.format(
        today=today_str,
        global_ctx=json.dumps(global_ctx, ensure_ascii=False, indent=2),
    )
    return _call_llm_json(prompt, max_tokens=4000)


# ---------------- 对外入口 ----------------

def analyze_boards(structured_news: dict, history: list, today_str: str) -> dict:
    history_summary = json.dumps(history[-7:], ensure_ascii=False, indent=2)

    # 逐板块分析：空板块不调 API，直接 fallback
    board_analysis_map = {}
    for board_id in BOARD_ORDER:
        items = structured_news.get("news", {}).get(board_id, []) or []
        print(f"[INFO] Analyzing board: {board_id} ({len(items)} items)")
        try:
            board_analysis_map[board_id] = _analyze_single_board(
                board_id, items, history_summary, today_str
            )
        except Exception as e:
            print(f"[ERROR] Board {board_id} analysis failed: {e}")
            board_analysis_map[board_id] = {
                "status": "解析失败",
                "analysis": [f"{BOARD_NAMES.get(board_id, board_id)}板块今日解析生成失败。"],
                "outlook": ["暂无展望。"],
            }

    # 全局总结
    print("[INFO] Generating global summary...")
    try:
        global_result = _analyze_global(structured_news, board_analysis_map, today_str)
    except Exception as e:
        print(f"[ERROR] Global summary failed: {e}")
        global_result = {
            "lede": "今日全局判断生成失败，请查看各板块解析。",
            "linkage_conclusion": "暂无联动结论。",
            "summary": [{"title": "说明", "body": "全局总结生成失败，各板块解析仍可查看。"}],
        }

    return {
        "lede": global_result.get("lede", ""),
        "boards": board_analysis_map,
        "linkage_conclusion": global_result.get("linkage_conclusion", ""),
        "summary": global_result.get("summary", []),
    }