# AI产业情报局 · 每日自动资讯看板

每日自动抓取芯片、存储、AI 大模型、Agent、AI 硬件、AI 短剧六个板块的最新资讯，
由 DeepSeek 生成结构化资讯 + 深度产业解析，渲染为静态 HTML 并部署到 GitHub Pages。

## 架构
GitHub Actions (每日 UTC 00:00)
→ scripts/fetcher.py 抓取 RSS，按板块关键词过滤、URL 去重
→ scripts/analyzer.py DeepSeek 两步分析：

1. 原始资讯 → 结构化（title/tag/summary/source/url）

2. 结构化资讯 + 最近7天判断 → 板块解析、lede、联动、总结
→ scripts/renderer.py Jinja2 渲染 templates/index.html.j2
→ dist/index.html
→ git commit + push
→ GitHub Pages 自动部署


## 快速开始

### 1. 创建仓库并上传本项目

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/<your-name>/ai-industry-dashboard.git
git push -u origin main