# QQ Chat Agent

## 简介

这是一个基于 Flask 的轻量级 QQ 聊天代理服务，提供关键词触发、素材库调度与 AI 对话能力的 webhook 后端和简单管理面板。

- 支持通过 `zhipuai` 客户端接入 GLM 系列模型（示例中使用 `glm-4-flash`）进行对话和意图判定。
- 支持“素材库”功能：可以配置多个资源库（图片/文件/文本/视频等），并由 AI 判断是否命中并返回对应素材。
- 提供基于关键词的自动回复功能（content.json），以及每个账号/群的独立配置（accounts.json）。
- 带有简单的前端管理面板：`/`（管理页面）与 `/assets`（素材库管理），通过浏览器方便配置。

项目结构示例：

- `main.py`：Flask 应用主入口，定义 webhook、管理 API 与前端路由。
- `templates/`：前端管理面板模板（`admin.html`, `assets.html`）。
- `config/`：运行时配置目录，包含 `accounts.json`, `content.json`, `assets.json`, `history.json`。
- `requirements.txt`：Python 依赖。

## 快速开始

1. 克隆仓库并进入目录：

```bash
git clone https://github.com/calcury/qq_chat_agent
cd qq_chat_agent
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 编辑 `main.py` 中的 `API_KEY` 与 `ORIGIN`：

- `API_KEY`：填入你的 `zhipuai` API Key。
- `ORIGIN`：静态资源基准 URL（如果素材使用本地路径或通过外部 URL 替换为合适前缀）。

4. 运行服务：

```bash
python main.py
```

默认情况下 Flask 会在 `127.0.0.1:5000` 上运行。你可以使用反向代理或将其部署到支持的主机上，并将 QQ 机器人的 webhook 指向 `/webhook` 路由。

## 配置说明

- `config/accounts.json`：按群号或 QQ 号作为 key 配置，示例字段：
	- `enabled`: 开关
	- `ai_enabled`: 是否启用 AI 回复
	- `reply_mode`: `at`/`always`/`agent`
	- `assets_enabled`: 是否启用素材库调度
	- `selected_assets`: 选择要调度的素材库名称数组
	- `ai_prompt`: AI 的 system prompt（人设）

- `config/content.json`：关键词组与回复内容，管理面板中称为关键词库（Content）。

- `config/assets.json`：素材库分组，每个分组为条目数组，条目包含：`desc`, `type`（image/file/video/text/link）, `path`（URL 或本地路径或文本内容）。

- `config/history.json`：运行时对话历史，用于 Agent 决策与上下文。

## 路由

- `GET /`：管理面板（`admin.html`）。
- `GET /assets`：素材管理页面（`assets.html`）。
- `POST /webhook`：接收来自 QQ 机器人或中间件的消息推送（主要业务入口）。
- `GET /api/config`：读取当前 `accounts` 与 `content` 配置（用于前端加载）。
- `POST /api/accounts`：保存 `accounts.json`。
- `POST /api/content`：保存 `content.json`。
- `GET|POST /api/assets`：获取/保存 `assets.json`。

## 注意事项

- 请妥善保管 `API_KEY`，避免泄漏。
- `zhipuai` 模型调用受限于你账户的配额与速率，部署前请确认可用配额。
- 如果将 `ORIGIN` 置为空，请确保存储在 `assets.json` 中的 `path` 字段为可被外网访问的完整 URL，或在部署时配置静态文件服务。
- 项目为示例性质，生产环境请添加认证、日志、异常监控与更严密的安全控制。

---

## English Version

### Overview

QQ Chat Agent is a lightweight Flask-based webhook backend for QQ bots. It supports keyword-triggered replies, an asset dispatch system, and AI-powered responses using the `zhipuai` client (e.g., `glm-4-flash`). A simple web admin UI is included to manage accounts, keyword content, and asset databases.

### Quick Start

1. Clone and install dependencies:

```bash
git clone <repo-url>
cd qq_chat_agent
pip install -r requirements.txt
```

2. Configure `main.py`:

- Set `API_KEY` to your `zhipuai` API key.
- Optionally set `ORIGIN` to a base URL for static assets.

3. Run the app:

```bash
python main.py
```

Send your QQ bot webhook to `POST /webhook`. The admin panel is available at `/` and the assets manager at `/assets`.

### Config Files

- `config/accounts.json`: Per-account/group configuration (enable flags, AI and asset settings, reply mode, AI prompt, etc.).
- `config/content.json`: Keyword groups and reply mappings.
- `config/assets.json`: Asset databases (entries with `desc`, `type`, `path`).
- `config/history.json`: Runtime conversation history.

### Endpoints

- `GET /` - Admin UI
- `GET /assets` - Assets manager UI
- `POST /webhook` - Webhook entry for messages
- `GET /api/config` - Read accounts & content
- `POST /api/accounts` - Save accounts
- `POST /api/content` - Save content
- `GET|POST /api/assets` - Get/Save assets

### Security & Deployment Notes

- Keep your API keys secret and avoid committing them to the repo.
- Test model usage and quota before production.
- Consider adding authentication on admin routes and HTTPS in production.
