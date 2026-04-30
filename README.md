# ai-auto-fix

基于 Flask 的自动化错误修复与 Commit 审查系统。接收外部项目推送的错误日志和 Git Commit 信息，由后台调度器调用 Claude Code Agent 在独立 worktree 中自动完成代码修复或审查，并通过企业微信机器人推送处理结果。

## 核心能力

- **错误自动修复**：接收错误日志，AI 在隔离 worktree 中分析并修复，创建 `ai-bugfix/*` 分支
- **Commit 自动审查**：通过 Git hook 触发，AI 审查提交变更，发现问题后创建 `ai-review/*` 分支
- **项目管理**：注册被监控项目，自动创建/清理 AI worktree 和 post-commit hook
- **管理后台**：Web 界面查看错误、Commit、项目状态及处理详情
- **企业微信通知**：处理完成时推送消息，附带管理后台链接

## 技术栈

- Python 3.x
- Flask 2.x
- SQLAlchemy 2.x + SQLite
- pytest
- Claude Code Agent CLI

## 目录结构

```
auto-optimize/
├── app.py                 # Flask 应用入口
├── requirements.txt       # Python 依赖
├── pytest.ini            # pytest 配置
├── src/
│   ├── api_push.py       # 接收外部推送的 HTTP API
│   ├── api_admin.py      # 管理后台页面和管理 API
│   ├── database.py       # SQLAlchemy 数据库访问层
│   ├── model.py          # ORM 模型（Project / ErrorLog / CommitLog）
│   ├── scheduler.py      # 后台调度线程，定时轮询处理任务
│   ├── ai_bugfix.py      # 错误修复流程，调用 Agent 提交修复分支
│   ├── ai_review.py      # Commit 审查流程，调用 Agent 提交审查修复分支
│   ├── project_manager.py # 项目 worktree / hook / 分支管理
│   ├── prompts.py        # Agent 提示词模板
│   ├── tool.py           # 日志、响应封装、命令执行、Agent 调用工具
│   ├── notifier.py       # 企业微信机器人通知
│   └── config.py         # 项目配置（数据库路径、Agent 命令、通知密钥等）
├── templates/            # Jinja2 管理后台模板
├── tests/                # 单元测试
└── data/                 # SQLite 数据库及 hook 脚本
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）

创建 `.env` 文件：

```env
NOTIFIER_BOT_ID=your_bot_id
NOTIFIER_SECRET=your_secret
NOTIFIER_USER_ID=your_user_id
BASE_URL=http://localhost:3002
```

或修改 `src/config.py` 中的配置项。

### 3. 启动服务

```bash
python app.py
```

服务默认监听 `http://0.0.0.0:3002`

## 推送 API

### 接收错误日志

```bash
POST /api/push/error
Content-Type: application/json

{
  "project_name": "my-project",
  "error_content": "Traceback (most recent call last): ..."
}
```

### 接收 Commit 信息（由 post-commit hook 调用）

```bash
GET /api/push/commit?project=my-project&commit_id=abc123
```

## 管理后台

| 页面 | 路由 | 说明 |
|------|------|------|
| 统计概览 | `/` / `/admin/` | 项目、错误、Commit 统计 |
| 错误列表 | `/admin/errors` | 所有错误日志及状态 |
| 错误详情 | `/admin/errors/<id>` | 单条错误内容及修复详情 |
| Commit 列表 | `/admin/commits` | 所有 Commit 及审查状态 |
| Commit 详情 | `/admin/commits/<id>` | 单条 Commit 审查详情 |
| 项目管理 | `/admin/projects` | 注册、配置、清理项目 |

## 管理 API

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/admin/errors` | GET | 错误列表（分页） |
| `/api/admin/errors/<id>` | GET | 错误详情 |
| `/api/admin/errors/<id>/status` | POST | 更新错误状态/上下文 |
| `/api/admin/errors/<id>` | DELETE | 删除错误及关联 AI 分支 |
| `/api/admin/commits` | GET | Commit 列表（分页） |
| `/api/admin/commits/<id>` | GET | Commit 详情 |
| `/api/admin/commits/<id>/status` | POST | 更新 Commit 状态/上下文 |
| `/api/admin/commits/<id>` | DELETE | 删除 Commit 及关联 AI 分支 |
| `/api/admin/projects` | GET | 项目列表 |
| `/api/admin/projects` | POST | 添加项目并创建 worktree |
| `/api/admin/projects/<id>/setup` | POST | 重新设置项目 worktree |
| `/api/admin/projects/<id>` | DELETE | 清理项目 worktree 和 hook |
| `/api/admin/projects/path-info` | POST | 检查路径/分支信息 |

## 数据流

### 错误修复流程

1. 外部项目调用 `POST /api/push/error` 推送错误
2. 系统校验项目并写入 `error_logs` 表（状态 `pending`）
3. `scheduler` 定时调用 `ai_bugfix`
4. `ai_bugfix` 在 worktree 中切换分支、合并最新代码
5. Agent 根据提示词分析并修复代码
6. 修复成功 → 创建 `ai-bugfix/<error_id>` 分支并推送
7. 更新数据库状态，发送企业微信通知

### Commit 审查流程

1. 被监控项目的 `post-commit` hook 调用 `GET /api/push/commit`
2. 系统写入 `commit_logs` 表（状态 `pending`）
3. `scheduler` 定时调用 `ai_review`
4. `ai_review` 获取目标 Commit diff，调用 Agent 审查
5. 发现问题 → 创建 `ai-review/<commit_id>` 分支并推送
6. 更新数据库状态，发送企业微信通知

## 运行测试

```bash
# 运行全部测试
pytest

# 运行指定测试文件
pytest tests/test_database.py
pytest tests/test_tool.py
pytest tests/test_app.py
```

## 配置说明

关键配置位于 `src/config.py`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_CONFIG` | SQLite 数据库路径 | `sqlite:///data/logs.db` |
| `AI_WORKTREE_BRANCH` | AI worktree 基准分支 | `ai-worktree` |
| `AI_WORKTREES_PATH` | worktree 根目录 | `D:\project\ai_worktrees` |
| `AGENT_COMMAND` | 调用 Agent 的命令模板 | `claude --dangerously-skip-permissions -p ...` |
| `FETCH_INTERVAL_SECONDS` | 调度轮询间隔 | `60` 秒 |
| `BASE_URL` | 管理后台基础 URL | `http://localhost:3002` |
| `NOTIFIER_BOT_ID` | 企业微信机器人 ID | 从环境变量读取 |
| `NOTIFIER_SECRET` | 企业微信机器人密钥 | 从环境变量读取 |
| `NOTIFIER_USER_ID` | 企业微信用户 ID | 从环境变量读取 |

## 开发约定

- 数据库变更需同步更新 `model.py` 和 `database.py`
- API 响应使用 `src.tool.result()` 保持统一格式
- 命令执行统一使用 `src.tool.run_command()`，避免散落 `subprocess`
- Agent 调用统一经过 `src.tool.call_agent()` 和 `src/config.py` 的 `AGENT_COMMAND`
- 删除逻辑仅允许处理 `ai-*` 分支，禁止操作用户项目中的非 AI 分支
- 测试使用临时 SQLite 数据库，避免写入 `data/logs.db`
