# -*- coding: utf-8 -*-
"""
Agent 修复相关模块
"""
import json
import time
from datetime import datetime
from typing import Tuple

from . import config
from . import prompts, database, notifier
from .tool import log, run_command, get_project_config, get_project_working_path, call_agent
from .model import ErrorLog


def process_errors():
    db = database.get_database()
    pending_errors = db.get_pending_errors()
    for error in pending_errors:
        process_single_error(error)


def process_single_error(error_log: ErrorLog):
    """处理单个错误"""
    db = database.get_database()
    try:
        # 调用Claude Code修复
        project = get_project_config(error_log.project_name)
        project_path = get_project_working_path(project)
        res = ai_bugfix(project_path, error_log.error_content, project.main_branch, error_log.context)
        log('修复结果：', res)
        # 更新数据库
        if 'success' in res:
            status = "success" if int(res["success"]) == 1 else "failure"
            branch_name = res.get("branch", "")
            db.update_error_fix_result(
                error_log.id,
                branch_name=branch_name,
                status=status,
                fix_details=json.dumps(res, ensure_ascii=False)
            )
            if status == "success":
                notifier.notify_error_fixed(
                    error_id=error_log.id,
                    project_name=error_log.project_name,
                    error_message=error_log.error_message,
                    status=status,
                    branch_name=branch_name,
                    how_fix = res.get("how_fix", ""),
                    cause = res.get("cause", "")
                )
    except Exception as e:
        log(f"处理错误失败: {e}")
        # 检查是否是项目不存在的错误
        error_msg = str(e)
        if "项目不存在" in error_msg:
            # 项目不存在，直接标记为失败，不再重试
            status = "skipped"
            db.update_error_fix_result(
                error_log.id,
                branch_name="",
                status=status,
                fix_details=f"项目不存在: {error_log.project_name}"
            )
        else:
            # 其他错误，等待一段时间后继续
            time.sleep(10)


def ai_bugfix(project_path: str, error_content: str, main_branch: str = "master", context: str = None):
    """使用AI修复错误"""
    log("开始修复错误:", project_path, error_content[:100] + '...')
    # 在主分支代码基础上修改
    run_command(['git', 'restore', '.'], project_path)
    run_command(['git', 'switch', '-C', config.AI_WORKTREE_BRANCH], project_path)
    run_command(['git', 'merge', main_branch], project_path)
    prompt = prompts.FIX_ERROR_PROMPT.replace("{error_content}", error_content)
    if context:
        prompt = prompt.replace("{context}", f"\n<额外上下文>\n{context}\n</额外上下文>")
    else:
        prompt = prompt.replace("{context}", "")
    res = call_agent(project_path, prompt)
    obj = json.loads(res[1])
    if int(obj['success']) == 1:
        current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
        exp_name = obj["exception"].split('.')[-1]
        branch = f'ai-bugfix/{exp_name}-{current_time}'
        obj['branch'] = branch
        # 新建bug分支并提交
        run_command(['git', 'switch', '-c', branch], project_path)
        run_command(['git', 'add', '.'], project_path)
        run_command(['git', 'commit', '-m', 'ai_bugfix:' + obj['commit']], project_path)
        run_command(['git', 'switch', config.AI_WORKTREE_BRANCH], project_path)  # 回到默认分支
    return obj
