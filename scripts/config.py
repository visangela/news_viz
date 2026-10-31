from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DIST_DIR = ROOT / "dist"
TEMPLATE_PATH = ROOT / "templates" / "index.html.j2"

SOURCES_PATH = DATA_DIR / "sources.json"
NEWS_HISTORY_PATH = DATA_DIR / "news_history.json"
BOARD_STATE_PATH = DATA_DIR / "board_state.json"

# 只抓取过去 N 小时内发布的资讯
FETCH_WINDOW_HOURS = 26

# 每个板块每日最多保留的新闻条数
MAX_NEWS_PER_BOARD = 8

# news_history 保留天数
HISTORY_RETENTION_DAYS = 60

# 历史判断摘要保留天数
BOARD_STATE_RETENTION_DAYS = 7

# 板块固定顺序（决定页面和导航顺序）
BOARD_ORDER = ["chip", "memory", "llm", "agent", "hardware", "drama"]

# 板块的固定链路（用于联动板块渲染）
LINKAGE_CHAIN = ["chip", "memory", "llm", "agent", "hardware", "drama"]

# 固定的传导关系描述（结构性，不随每日变化）
LINKAGE_RELATIONS = [
    {
        "from": "chip", "to": ["memory", "hardware"], "color": "#2a4d69",
        "title": "芯片 → 存储 / 硬件",
        "text": "先进封装瓶颈、散热材料突破、HBM 产能售罄，共同决定了云端和端侧 AI 硬件的物理上限。"
    },
    {
        "from": "memory", "to": ["llm", "agent"], "color": "#9c2b22",
        "title": "存储 → 大模型 / Agent",
        "text": "存储原厂的超长景气判断与长约机制，约束了推理基础设施的成本下降速度，直接进入大模型价格战和 Agent ROI 的计算。"
    },
    {
        "from": "llm", "to": ["agent", "drama"], "color": "#5b4b6e",
        "title": "大模型 → Agent / AI 短剧",
        "text": "开源万亿参数模型降低了 Agent 和内容工具的底层能力获取成本，自托管多模态推理成为选项。"
    },
    {
        "from": "agent", "to": ["drama"], "color": "#4a5d43",
        "title": "Agent → AI 短剧",
        "text": "内容生产工作流的 Agent 化，把规划、工具调用和多模态生成打包进一站式创作，是 Agent 能力在创意产业最早规模化验证 ROI 的场景。"
    },
    {
        "from": "hardware", "to": ["agent", "chip"], "color": "#3d5a5c",
        "title": "硬件 → Agent / 芯片",
        "text": "端侧 Agent 常驻运行对统一内存容量、带宽、散热的需求，反向定义了芯片和封装的设计目标。"
    },
    {
        "from": "drama", "to": ["llm", "agent"], "color": "#8a6d3b",
        "title": "AI 短剧 → 大模型 / Agent",
        "text": "短剧行业的 AI 素材标识、生成物追溯、平台准入，为 Agent 的安全与透明度提供了最早的规模化监管样本。"
    }
]

ARCHIVE_PATH = DATA_DIR / "news_archive.json"
ARCHIVE_TEMPLATE_PATH = ROOT / "templates" / "archive.html.j2"

# 归档页面保留历史资讯的天数
ARCHIVE_RETENTION_DAYS = 90