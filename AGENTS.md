# AGENTS.md

本文件为 AI 代理（如 Claude Code）提供在本仓库中工作的指导。

## 项目概述

auto-optimize 是一个 AI 驱动的自动化错误修复和代码提交审查系统。它：
- 通过 HTTP API 接收错误日志和 git commit 信息
- 使用 Claude Code 代理自动修复代码中的错误
- 审查提交中的逻辑问题并进行修复
- 将所有数据存储在 SQLite 数据库中

## 核心架构

### 主要组件

| 组件 | 文件 | 用途 |
| ---- | ---- | ---- |
| Flask 应用 | `app.py` | 主入口，启动 HTTP 服务器和调度器 |
| 调度器 | `src/scheduler.py` | 后台线程，定期处理错误和提交 |
| API 推送 | `src/api_push.py` | HTTP 端点：`/api/push/error` 和 `/api/push/commit` |
| 管理后台 | `src/api_admin.py` | 页面路由和管理 API |
| 数据库 | `src/database.py` | SQLite 的 SQLAlchemy ORM 层 |
| 数据模型 | `src/model.py` | 数据模型：`CommitLog`、`ErrorLog`、`Project` |
| AI 修复器 | `src/ai_fixer.py` | 使用 Claude 修复错误并创建修复分支 |
| AI 审查器 | `src/ai_reviewer.py` | 使用 Claude 审查提交中的问题 |
| 提示词 | `src/prompts.py` | 用于修复和审查的 LLM 提示词 |
| 工具 | `src/tool.py` | 实用函数（日志记录、命令执行等） |

### 管理后台页面路由

| 路由 | 页面 | 模板文件 |
|------|------|----------|
| `GET /` | 首页/概览 | `templates/index.html` |
| `GET /admin/` | 首页/概览（备用） | `templates/index.html` |
| `GET /admin/errors` | 错误记录列表 | `templates/errors.html` |
| `GET /admin/errors/<id>` | 错误详情 | `templates/error_detail.html` |
| `GET /admin/commits` | Commit 审查列表 | `templates/commits.html` |
| `GET /admin/commits/<id>` | Commit 详情 | `templates/commit_detail.html` |
| `GET /admin/projects` | 工程管理 | `templates/projects.html` |

### 管理 API 接口

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/admin/errors` | GET | 获取错误列表（分页） |
| `/api/admin/errors/<id>` | GET | 获取单个错误详情 |
| `/api/admin/commits` | GET | 获取 Commit 列表（分页） |
| `/api/admin/commits/<id>` | GET | 获取单个 Commit 详情 |
| `/api/admin/projects` | GET | 获取所有项目列表 |
| `/api/admin/projects` | POST | 添加新项目 |
| `/api/admin/projects/<id>/setup` | POST | 重新设置项目 |
| `/api/admin/projects/<id>` | DELETE | 删除/清理项目 |

### 数据流

1. 错误/提交推送 → `api_push.py` → 存储在 SQLite 中
2. 调度器每隔 `FETCH_INTERVAL_SECONDS` 运行一次（默认 60 秒）
3. `ai_fixer.py` 处理待处理的错误 → 创建 `ai-fix/*` 分支
4. `ai_reviewer.py` 处理待处理的提交 → 创建 `ai-review/*` 分支

## 常用开发命令

### 运行应用

```bash
python app.py
```

Flask 服务器将在 `http://0.0.0.0:3002` 上启动

### 运行测试

```bash
pytest
```

pytest 配置默认忽略 `test_report_fix.py`（参见 `pytest.ini`）。

运行特定测试文件：

```bash
pytest tests/test_database.py
pytest tests/test_tool.py
```

## 配置

`config.py` 中的关键配置：

- `DATABASE_CONFIG`：SQLite 数据库路径（默认：`sqlite:///data/logs.db`）
- `AI_WORKTREE_BRANCH`：AI 操作的工作分支（默认：`ai-worktree`）
- `AGENT_COMMAND`：Claude Code 代理命令模板
- `FETCH_INTERVAL_SECONDS`：调度器轮询间隔（默认 60）
- `PROJECT_CONFIG`：受监控项目的列表，包含路径和主分支

## 需要了解的关键文件

| 路径 | 说明 |
| ---- | ---- |
| `config.py` | 中央配置 - 编辑此文件以添加/修改项目 |
| `src/prompts.py` | 更新用于错误修复和提交审查的 LLM 提示词 |
| `src/database.py` | 数据库架构和操作 |
| `src/ai_fixer.py` 和 `src/ai_reviewer.py` | 核心 AI 逻辑 |

## 注意

修改完代码后不要启动服务, 我自己手动启动服务