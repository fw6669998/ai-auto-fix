# -*- coding: utf-8 -*-
"""
工具方法模块
"""
import hashlib
import os
import subprocess
from datetime import datetime
from typing import Tuple

from flask import jsonify

from . import config


def log(*args, **kwargs):
    curTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(curTime, ': ', *args, **kwargs)


def result(data=None, msg=None, success=True):
    res1 = jsonify({
        "data": data,
        "success": success,
        "msg": msg
    })
    return res1


def error(msg=None, error_code=500):
    return result(None, msg, False), error_code


def get_project_config(project_name=None):
    """获取项目配置对象"""
    from .database import get_database
    db = get_database()
    project = db.get_project_by_name(project_name)
    if project is None:
        raise Exception(f"项目不存在: {project_name}")
    return project


def get_project_working_path(project) -> str:
    """获取AI执行修复/评审使用的项目工作树路径。"""
    worktree_path = getattr(project, "worktree_path", None)
    if not worktree_path:
        worktree_path = os.path.join(config.AI_WORKTREES_PATH, project.project_name)
    if not os.path.exists(worktree_path):
        raise Exception(f"项目工作树不存在: {worktree_path}，请先在工程管理中设置项目")
    return worktree_path


def compute_error_hash(error_content: str) -> str:
    """计算错误内容MD5哈希"""
    return hashlib.md5(error_content.encode('utf-8')).hexdigest()


def run_command(command, cwd: str = None) -> Tuple[int, str, str]:
    """执行Shell命令"""
    try:
        commandStr = " ".join(command)
        if len(commandStr) > 50:
            commandStr = commandStr[:50] + "..."
        log('执行命令:', commandStr)
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
            encoding='utf-8',
            errors='replace'
        )
        stdout_preview = result.stdout[:100] if result.stdout else ""
        stderr_preview = result.stderr[:100] if result.stderr else ""
        log('命令结果:', stdout_preview, stderr_preview)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        raise Exception(f"执行命令失败: {e}")
        # return -1, "", str(e)


def call_agent(project_path: str, prompt: str):
    """调用AI Agent"""
    command = []
    for item in config.AGENT_COMMAND:
        if item == "{prompt}":
            command.append(prompt)
        else:
            command.append(item)
    res = run_command(command, project_path)
    return res


def get_commit_message(project_name: str, commit_id: str) -> str:
    """获取commit的message"""
    from .database import get_database
    db = get_database()
    project = db.get_project_by_name(project_name)
    if project is None:
        return ""
    worktree_path = getattr(project, "worktree_path", None)
    if not worktree_path:
        return ""
    res = run_command(['git', 'log', '-1', '--pretty=format:%s', commit_id], worktree_path)
    return res[1] if res[0] == 0 else ""