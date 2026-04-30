# AGENTS.md

本文件为 AI 代理在本仓库中工作提供项目级指导。

## 项目概述

`auto-optimize` 是一个基于 Flask 的自动化错误修复和 Commit 审查系统。它接收外部项目推送的错误日志和 Git Commit 信息，将记录写入 SQLite，并由后台调度器调用 Agent 在独立 worktree 中完成修复或审查。

核心能力：

- 通过 HTTP API 接收错误日志和 Commit 信息。
- 管理被监控项目及其 AI 工作树。
- 定时处理待修复错误并创建 `ai-bugfix/*` 分支。
- 定时审查待检查 Commit，发现问题后创建 `ai-review/*` 分支。
- 通过管理后台查看错误、Commit、项目状态和处理结果。
- 通过企业微信机器人发送处理通知。

## 技术栈

- Python
- Flask
- SQLAlchemy 2.x
- SQLite
- pytest
- Claude Code Agent 命令行调用

依赖定义在 `requirements.txt`。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `app.py` | Flask 应用入口，注册蓝图，启动通知器、调度器和 Web 服务 |
| `src/api_push.py` | 接收外部错误和 Commit 推送的 API |
| `src/api_admin.py` | 管理后台页面路由和管理 API |
| `src/database.py` | SQLAlchemy 数据库访问层和兼容迁移逻辑 |
| `src/model.py` | ORM 模型：`Project`、`ErrorLog`、`CommitLog` |
| `src/scheduler.py` | 后台调度线程，定时处理错误和 Commit |
| `src/ai_bugfix.py` | 错误修复流程，调用 Agent 并提交修复分支 |
| `src/ai_review.py` | Commit 审查流程，调用 Agent 并提交审查修复分支 |
| `src/project_manager.py` | 项目 worktree 创建、清理和 post-commit hook 管理 |
| `src/prompts.py` | Agent 提示词模板 |
| `src/tool.py` | 日志、响应封装、命令执行和 Agent 调用工具 |
| `src/notifier.py` | 企业微信通知相关逻辑 |
| `templates/` | 管理后台 Jinja2 模板 |
| `tests/` | 单元测试 |
| `data/` | 本地运行数据和 hook 脚本 |

## 运行命令

安装依赖：

```bash
pip install -r requirements.txt
```

运行应用：

```bash
python app.py
```

服务默认监听：

```text
http://0.0.0.0:3002
```

运行测试：

```bash
pytest
```

运行单个测试文件：

```bash
pytest tests/test_database.py
pytest tests/test_tool.py
pytest tests/test_app.py
```

`pytest.ini` 当前配置为 `-s --ignore=tests/test_report_fix.py`。

## 主要路由

页面路由：

| 路由 | 说明 | 模板 |
| --- | --- | --- |
| `GET /` | 统计概览 | `templates/index.html` |
| `GET /admin/` | 管理首页 | `templates/index.html` |
| `GET /admin/errors` | 错误列表 | `templates/errors.html` |
| `GET /admin/errors/<id>` | 错误详情 | `templates/error_detail.html` |
| `GET /admin/commits` | Commit 列表 | `templates/commits.html` |
| `GET /admin/commits/<id>` | Commit 详情 | `templates/commit_detail.html` |
| `GET /admin/projects` | 项目管理 | `templates/projects.html` |

推送 API：

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/push/error` | POST | 接收错误日志，必填 `project_name` 和 `error_content` |
| `/api/push/commit` | GET | 接收 Commit 信息，必填 `project` 和 `commit_id` |

管理 API：

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/admin/errors` | GET | 错误列表分页查询 |
| `/api/admin/errors/<id>` | GET | 错误详情 |
| `/api/admin/errors/<id>/status` | POST | 更新错误状态和上下文 |
| `/api/admin/errors/<id>` | DELETE | 删除错误记录及关联 AI 分支 |
| `/api/admin/commits` | GET | Commit 列表分页查询 |
| `/api/admin/commits/<id>` | GET | Commit 详情 |
| `/api/admin/commits/<id>/status` | POST | 更新 Commit 状态和上下文 |
| `/api/admin/commits/<id>` | DELETE | 删除 Commit 记录及关联 AI 分支 |
| `/api/admin/projects` | GET | 项目列表 |
| `/api/admin/projects` | POST | 添加项目并异步创建 worktree |
| `/api/admin/projects/<id>/setup` | POST | 重新设置项目 worktree |
| `/api/admin/projects/<id>` | DELETE | 清理项目 worktree 和 hook |
| `/api/admin/projects/path-info` | POST | 检查路径、目录名和 Git 分支信息 |

## 数据流

错误修复流程：

1. 外部项目调用 `/api/push/error` 推送错误。
2. `src/api_push.py` 校验项目并写入 `error_logs`。
3. `src/scheduler.py` 定时调用 `src/ai_bugfix.py`。
4. `ai_bugfix` 在项目 worktree 中切换到 `AI_WORKTREE_BRANCH`，合并主分支。
5. Agent 根据 `FIX_ERROR_PROMPT` 修改代码。
6. 修复成功时创建 `ai-bugfix/*` 分支并提交。
7. 数据库记录处理状态，必要时发送通知。

Commit 审查流程：

1. 被监控项目的 `post-commit` hook 调用 `/api/push/commit`。
2. `src/api_push.py` 写入 `commit_logs`。
3. `src/scheduler.py` 定时调用 `src/ai_review.py`。
4. `ai_review` 获取目标 Commit diff 并调用 Agent。
5. 发现并修复问题时创建 `ai-review/*` 分支并提交。
6. 数据库记录审查状态，必要时发送通知。

## 配置

关键配置在 `src/config.py`：

| 配置 | 说明 |
| --- | --- |
| `DATABASE_CONFIG` | SQLite 连接字符串，默认 `sqlite:///data/logs.db` |
| `AI_WORKTREE_BRANCH` | AI worktree 使用的基准分支 |
| `AI_WORKTREES_PATH` | 所有项目 AI worktree 的根目录 |
| `AGENT_COMMAND` | 调用 Agent 的命令模板，`{prompt}` 会被替换为提示词 |
| `FETCH_INTERVAL_SECONDS` | 调度器轮询间隔 |
| `BASE_URL` | 管理后台基础 URL，用于通知链接 |
| `NOTIFIER_*` | 企业微信通知配置 |

注意：`src/config.py` 可能包含本地路径和通知密钥。修改时避免把真实密钥扩散到日志、文档或测试输出中。

## 开发约定

- 保持中文注释和用户可见文案的既有风格。
- 数据库变更应同步更新 `src/model.py`、`src/database.py` 的兼容迁移逻辑，以及相关测试。
- API 响应优先使用 `src.tool.result()` 保持统一格式。
- 命令执行优先使用 `src.tool.run_command()`，不要在业务代码中散落 `subprocess` 调用。
- Agent 调用统一经过 `src.tool.call_agent()` 和 `src/config.py` 的 `AGENT_COMMAND`。
- 修改模板时同步检查对应的 `src/api_admin.py` 页面参数和 JSON API。
- 不要随意删除或重建用户项目中的非 AI 分支；删除逻辑仅允许处理 `ai-*` 分支。
- 不要改动用户未要求的格式化、重命名或大范围重构。

## 测试注意事项

- 文档或模板小改可以只做针对性检查。
- 涉及数据库、状态流转、API 参数、路由行为时运行 `pytest` 或相关测试文件。
- 涉及 Agent、Git worktree 或 hook 的逻辑时，优先补充隔离测试，避免依赖真实外部项目路径。
- 测试中应使用临时 SQLite 数据库，不要写入 `data/logs.db`。

## 给代理的工作约束

- 修改代码后不要自动启动长期运行的 Flask 服务，用户会手动启动。
- 不要覆盖用户当前未提交的改动；如果同一文件已有用户改动，先读清楚再在其基础上调整。
- 不要执行破坏性 Git 命令，例如 `git reset --hard`、强制 checkout 或清理未跟踪文件，除非用户明确要求。
- 不要修改被管理项目的真实 worktree、hook 或分支，除非任务明确要求验证这些流程。
- 对涉及通知密钥、路径和本地环境的改动保持最小化。
