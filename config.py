# -*- coding: utf-8 -*-
"""
配置模块 - 项目配置文件
"""
# 数据库配置
DATABASE_CONFIG = "sqlite:///data/logs.db"

AI_WORKTREE_BRANCH = "ai-worktree"

AI_WORKTREES_PATH = r"D:\project\ai_worktrees"

# 处理代码任务的agent命令
AGENT_COMMAND = ["claude", "--dangerously-skip-permissions", "-p", '{prompt}']

# 多少秒处理一条任务
FETCH_INTERVAL_SECONDS = 60

PROJECT_CONFIG = [
    {
        "project_name": "app1",
        # 项目路径,建议使用worktree项目路径,worktree分支为ai-base
        "project_path": f'C:\\Users\\fw666\\OneDrive\\auto-optimize\\tests\\app1-ai-base',
        "main_branch": "master",  # 主分支
    }
]
