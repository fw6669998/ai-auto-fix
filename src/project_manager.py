# -*- coding: utf-8 -*-
"""
项目管理模块 - 管理git worktree和post-commit hook
"""
import os
import stat
import shutil
from pathlib import Path
from typing import Tuple, Optional

from . import config
from .tool import run_command, log
from .database import get_database


POST_COMMIT_SCRIPT = '''#!/bin/bash
# Auto-optimize AI post-commit hook

# 获取commit信息
COMMIT_ID=$(git rev-parse --short HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# 如果是ai-开头的分支，不触发
if [[ "$BRANCH" =~ ^ai- ]]; then
    exit 0
fi

# 获取最新提交的提交信息
COMMIT_MSG=$(git log -1 --pretty=%B)
# 如果提交信息中包含 ai_fix / ai_review / ai_ignore 则忽略
case "$COMMIT_MSG" in
  *ai_fix*|*ai_review*|*ai_ignore*)
    echo "[post-commit] ignored: commit message contains ai_fix / ai_review / ai_ignore"
    exit 0
    ;;
esac

# 发送请求
curl -s -o /dev/null -m 5 \
  "http://127.0.0.1:3002/api/push/commit?project={project_name}&commit_id=$COMMIT_ID"
exit 0
'''


def get_worktree_path(project_name: str) -> str:
    """获取项目worktree路径"""
    return os.path.join(config.AI_WORKTREES_PATH, project_name)


def setup_project(project_id: int) -> Tuple[bool, str]:
    """
    设置项目：创建worktree并配置post-commit hook

    Returns: (success, message)
    """
    db = get_database()
    project = db.get_project_by_id(project_id)
    if not project:
        return False, "项目不存在"

    try:
        # 更新状态为处理中
        db.update_project_status(project_id, "setting", "正在创建工作树...")

        # 检查源项目路径是否存在
        source_path = Path(project.project_path)
        if not source_path.exists():
            raise Exception(f"项目路径不存在: {project.project_path}")

        # 检查是否是git仓库
        git_dir = source_path / ".git"
        if not git_dir.exists():
            raise Exception(f"不是git仓库: {project.project_path}")

        # 创建worktree目录
        worktree_path = Path(project.worktree_path or get_worktree_path(project.project_name))

        # 先清理 git 中可能残留的 worktree 注册信息（即使目录不存在）
        if source_path.exists() and (source_path / ".git").exists():
            # 尝试 remove --force 清理
            remove_cmd = ["git", "worktree", "remove", "--force", str(worktree_path)]
            run_command(remove_cmd, cwd=str(source_path))
            # 运行 prune 清理所有丢失的 worktree
            prune_cmd = ["git", "worktree", "prune"]
            run_command(prune_cmd, cwd=str(source_path))

        # 如果目录存在，删除它
        if worktree_path.exists():
            # 删除目录，带重试
            for i in range(3):
                try:
                    shutil.rmtree(worktree_path, ignore_errors=False)
                    break
                except Exception:
                    import time
                    time.sleep(0.5)
            # 最后确认删除
            if worktree_path.exists():
                raise Exception(f"无法删除已存在的worktree目录: {worktree_path}")

        # 创建worktree父目录
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        db.update_project_worktree_path(project_id, str(worktree_path))

        # 创建git worktree
        log(f"创建worktree: {project.project_name} -> {worktree_path}")

        # 检查并创建worktree分支（如果不存在）
        branch_name = config.AI_WORKTREE_BRANCH
        check_cmd = ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"]
        code, _, _ = run_command(check_cmd, cwd=str(source_path))
        if code != 0:
            # 分支不存在，创建一个
            create_cmd = ["git", "checkout", "-b", branch_name]
            code, _, _ = run_command(create_cmd, cwd=str(source_path))
            if code != 0:
                # 如果创建失败，尝试基于主分支创建
                create_cmd = ["git", "checkout", "-b", branch_name, project.main_branch]
                code, _, _ = run_command(create_cmd, cwd=str(source_path))
                if code != 0:
                    raise Exception(f"无法创建worktree分支 {branch_name}")

        # 回到主分支
        checkout_cmd = ["git", "checkout", project.main_branch]
        run_command(checkout_cmd, cwd=str(source_path))

        # 创建worktree
        worktree_cmd = ["git", "worktree", "add", str(worktree_path), branch_name]
        code, _, stderr = run_command(worktree_cmd, cwd=str(source_path))
        if code != 0:
            # 如果失败，尝试 prune 后用 -f 强制添加
            log(f"首次创建worktree失败，尝试强制模式: {stderr}")
            prune_cmd = ["git", "worktree", "prune"]
            run_command(prune_cmd, cwd=str(source_path))

            worktree_cmd = ["git", "worktree", "add", "-f", str(worktree_path), branch_name]
            code, _, stderr = run_command(worktree_cmd, cwd=str(source_path))
            if code != 0:
                raise Exception(f"创建worktree失败: {stderr}")

        # 设置post-commit hook - 在源项目git目录中
        hooks_dir = source_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        post_commit_path = hooks_dir / "post-commit"

        log(f"配置post-commit: {post_commit_path}")
        with open(post_commit_path, "w", encoding="utf-8") as f:
            f.write(POST_COMMIT_SCRIPT.format(project_name=project.project_name))

        # 设置执行权限
        os.chmod(post_commit_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
                 stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

        # 更新状态为active
        db.update_project_status(project_id, "active", f"工作树已创建: {worktree_path}")
        return True, "项目设置成功"

    except Exception as e:
        log(f"设置项目失败: {e}")
        db.update_project_status(project_id, "failed", str(e))
        return False, str(e)


def cleanup_project(project_id: int) -> Tuple[bool, str]:
    """
    清理项目：删除worktree和post-commit hook

    Returns: (success, message)
    """
    db = get_database()
    project = db.get_project_by_id(project_id)
    if not project:
        return False, "项目不存在"

    try:
        # 更新状态
        db.update_project_status(project_id, "cleaning", "正在清理...")

        source_path = Path(project.project_path)
        worktree_path = Path(project.worktree_path or get_worktree_path(project.project_name))

        # 删除源项目中的post-commit hook
        post_commit_path = source_path / ".git" / "hooks" / "post-commit"
        if post_commit_path.exists():
            log(f"删除post-commit hook: {post_commit_path}")
            post_commit_path.unlink()

        # 清理git worktree
        if source_path.exists() and (source_path / ".git").exists():
            log(f"清理worktree: {worktree_path}")
            remove_cmd = ["git", "worktree", "remove", str(worktree_path)]
            run_command(remove_cmd, cwd=str(source_path))

            # 尝试删除分支
            branch_name = config.AI_WORKTREE_BRANCH
            delete_cmd = ["git", "branch", "-D", branch_name]
            run_command(delete_cmd, cwd=str(source_path))

        # 删除worktree目录
        if worktree_path.exists():
            log(f"删除工作目录: {worktree_path}")
            shutil.rmtree(worktree_path, ignore_errors=True)

        # 删除数据库记录
        db.delete_project(project_id)

        return True, "项目清理成功"

    except Exception as e:
        log(f"清理项目失败: {e}")
        db.update_project_status(project_id, "failed", f"清理失败: {e}")
        return False, str(e)
