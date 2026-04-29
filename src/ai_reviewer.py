# -*- coding: utf-8 -*-
"""
Commit 检查模块 - 检查 git commit 是否存在严重逻辑错误，发现问题后直接修复
"""
import json
from datetime import datetime

import config
from src.tool import log, run_command, get_project_config, get_project_working_path, call_agent
from src import database, prompts
from src.model import CommitLog


def process_commits():
    log('定时执行commit检查')
    db = database.get_database()
    pending_commits = db.get_pending_commits()
    for commit in pending_commits:
        process_single_commit(commit)


def process_single_commit(commit_log: CommitLog):
    """处理单个commit检查：检测+修复一次完成"""
    db = database.get_database()
    try:
        project = get_project_config(commit_log.project_name)
        project_path = get_project_working_path(project)
        obj = ai_review(project_path, commit_log.commit_id, project.main_branch, commit_log.context)
        if 'has_issue' in obj:
            db.update_commit_check_result(
                commit_log.id,
                check_status="success",
                check_result="has_issue" if int(obj["has_issue"]) == 1 else "no_issue",
                check_details=json.dumps(obj, ensure_ascii=False)
            )
    except Exception as e:
        log(f"检查commit失败: {e}")
        error_msg = str(e)
        # 不管什么原因，只要失败就标记检查结果，避免重复处理
        db.update_commit_check_result(
            commit_log.id,
            check_status="failure",
            check_result="skipped",  # 标记为跳过，避免重复处理
            check_details=str(e)
        )


def ai_review(project_path: str, commit_id: str, main_branch: str = "master", context: str = None):
    """使用AI检测并修复commit中的逻辑错误"""
    diff = get_commit_diff(project_path, commit_id)
    if not diff:
        return None

    log("开始检测并修复commit逻辑:", diff[:100] + '...')
    ai_base_branch = config.AI_WORKTREE_BRANCH
    run_command(['git', 'restore', '.'], project_path)
    run_command(['git', 'switch', '-C', ai_base_branch], project_path)
    run_command(['git', 'merge', main_branch], project_path)

    prompt = prompts.CHECK_COMMIT_PROMPT.replace("{diff}", diff)
    if context:
        prompt = prompt.replace("{context}", f"\n<额外上下文>\n{context}\n</额外上下文>")
    else:
        prompt = prompt.replace("{context}", "")
    res = call_agent(project_path, prompt)
    log('commit检测修复结果：', res)

    try:
        obj = json.loads(res[1])
    except Exception as e:
        raise ValueError(f"解析结果失败: {str(e)}\n原始结果: {res[1]}")

    commit_msg = get_commit_message(project_path, commit_id)
    has_issue = "1" if str(obj.get("has_issue", "0")) == "1" else "0"

    if has_issue == "1" and int(obj.get("success", "0")) == 1 and obj.get("severity", "").lower() == "high":
        current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch = f'ai-review/{commit_id}-{current_time}'
        obj['branch'] = branch
        run_command(['git', 'switch', '-c', branch], project_path)
        run_command(['git', 'add', '.'], project_path)
        run_command(['git', 'commit', '-m', 'ai_review:' + commit_msg], project_path)
        run_command(['git', 'switch', ai_base_branch], project_path)
        log(f"已提交修复分支: {branch}")

    return obj


def get_commit_diff(project_path: str, commit_id: str) -> str:
    """获取commit的diff内容"""
    res = run_command(['git', 'show', commit_id], project_path)
    if res[0] == 0:
        return res[1]
    return ""


def get_commit_message(project_path: str, commit_id: str) -> str:
    """获取commit的message"""
    res = run_command(['git', 'log', '-1', '--pretty=format:%s', commit_id], project_path)
    if res[0] == 0:
        return res[1]
    return "xxx"
