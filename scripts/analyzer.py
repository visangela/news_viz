import json
import os
from datetime import datetime

from openai import OpenAI

from scripts.config import BOARD_ORDER

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

MODEL = "deepseek-chat"

SYSTEM_PROMPT = (
    "你是「AI产业情报局」的资深产业分析师。"
    "你的任务是把零散的资讯整合成有判断力的产业分析，而不是简单拼凑新闻。"
    "输出必须是严格的 JSON 对象，不包含任何解释性文字、markdown 代码块标记或注释。"
)

NEWS_STRUCT_PROMPT = """今天是 {today}。以下是今天各板块抓取到的原始资讯（JSON）：

{news_json}

请为每一条资讯生成结构化版本，要求：
- 保留原文 URL 和 source
- title 精简到 12-25 字，突出最关键的产业信息
- summary 80-150 字，说明"发生了什么"和"为什么重要"
- tag 3-6 字，概括这条资讯的产业维度（如"散热材料""财报""开源""平台治理"）

严格输出如下 JSON（不要任何其他字段）：
{{
  "news": {{
    "{first_board}": [
      {{"title": "...", "summary": "...", "tag": "...", "url": "...", "source": "..."}}
    ]
  }}
}}

注意：只对实际传入的板块输出；如果某个板块今日无资讯，则输出空数组。"""

BOARD_ANALYSIS_PROMPT = """今天是 {today}。你是 AI 产业分析师。以下是今天各板块的结构化资讯：

{news_json}

各板块过去 7 天的判断摘要（供你判断今日信号是延续还是转折）：

{history_summary}

请输出每个板块的深度解析，要求：
1. status：4-6 字的板块状态标签（如"散热材料突围""短缺至 2030""治理落地"）
2. analysis：2 段分析，每段 100-180 字。要求：
   - 第一段：今日最值得注意的信号是什么？为什么重要？背后的产业结构性含义是什么？
   - 第二段：与近期趋势对比——是延续还是转折？涉及哪些产业链环节的博弈？
   - 不要复述新闻，要有判断
3. outlook：1-2 段展望，每段 100-180 字，中期（2027 年前）和长期（2028 年后）走向判断
4. lede：全局一句话判断，150-250 字，串联至少 3 个板块的共同信号
5. linkage_conclusion：共同矛盾分析，150-250 字
6. summary：6-7 条总总结，每条包含 title 和 body（body 100-200 字）

严格输出如下 JSON：
{{
  "lede": "...",
  "boards": {{
    "{first_board}": {{"status": "...", "analysis": ["...", "..."], "outlook": ["..."]}}
  }},
  "linkage_conclusion": "...",
  "summary": [
    {{"title": "...", "body": "..."}}
  ]
}}"""


def analyze_news(raw_news: dict, today_str: str) -> dict:
    news_json = json.dumps(raw_news, ensure_ascii=False, indent=2)
    prompt = NEWS_STRUCT_PROMPT.format(
        today=today_str,
        news_json=news_json,
        first_board=BOARD_ORDER[0],
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.6,
        max_tokens=4000,
    )
    return json.loads(resp.choices[0].message.content)


def analyze_boards(structured_news: dict, history: list, today_str: str) -> dict:
    news_json = json.dumps(structured_news, ensure_ascii=False, indent=2)
    history_json = json.dumps(history[-7:], ensure_ascii=False, indent=2)
    prompt = BOARD_ANALYSIS_PROMPT.format(
        today=today_str,
        news_json=news_json,
        history_summary=history_json,
        first_board=BOARD_ORDER[0],
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=8000,
    )
    return json.loads(resp.choices[0].message.content)