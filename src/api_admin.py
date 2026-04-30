# -*- coding: utf-8 -*-
"""
管理后台API模块 - 页面路由和数据接口
"""
import os
from pathlib import Path
from typing import Tuple

from flask import Blueprint, render_template, request, jsonify

from src import config
from src.database import get_database
from src.tool import result, log, run_command
from src.project_manager import setup_project, cleanup_project

admin_api = Blueprint('admin_api', __name__, url_prefix='/')


def _normalize_filter(value):
    """Normalize optional query filters from pages and API calls."""
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() in ("none", "null"):
        return None
    return value


# ---------- 页面路由 ----------

@admin_api.route('/admin/')
def index():
    """管理首页 - 统计概览"""
    db = get_database()
    stats = db.get_stats()
    return render_template('index.html', stats=stats)


@admin_api.route('/admin/errors')
def errors():
    """错误记录列表页"""
    page = request.args.get('page', 1, type=int)
    status = _normalize_filter(request.args.get('status', None))
    project_name = _normalize_filter(request.args.get('project_name', None))
    return render_template('errors.html', page=page, status=status, project_name=project_name)


@admin_api.route('/admin/errors/<int:error_id>')
def error_detail(error_id):
    """错误详情页"""
    db = get_database()
    error = db.get_error_log_by_id(error_id)
    return render_template('error_detail.html', error=error)


@admin_api.route('/admin/commits')
def commits():
    """Commit审查记录列表页"""
    page = request.args.get('page', 1, type=int)
    status = _normalize_filter(request.args.get('status', None))
    project_name = _normalize_filter(request.args.get('project_name', None))
    return render_template('commits.html', page=page, status=status, project_name=project_name)


@admin_api.route('/admin/commits/<int:commit_id>')
def commit_detail(commit_id):
    """Commit详情页"""
    db = get_database()
    commit = db.get_commit_log_by_id(commit_id)
    return render_template('commit_detail.html', commit=commit)


@admin_api.route('/admin/projects')
def projects():
    """工程管理列表页"""
    return render_template('projects.html')


# ---------- API接口 ----------

@admin_api.route('/api/admin/errors')
def api_errors():
    """获取错误列表JSON"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = _normalize_filter(request.args.get('status', None))
    project_name = _normalize_filter(request.args.get('project_name', None))

    db = get_database()
    data = db.get_error_logs_paginated(page=page, per_page=per_page, status=status, project_name=project_name)

    return jsonify({
        "items": [item.to_dict() for item in data["items"]],
        "total": data["total"],
        "page": data["page"],
        "per_page": data["per_page"],
        "pages": data["pages"]
    })


@admin_api.route('/api/admin/errors/<int:error_id>')
def api_error_detail(error_id):
    """获取错误详情JSON"""
    db = get_database()
    error = db.get_error_log_by_id(error_id)
    if not error:
        return result(None, "记录不存在", False)
    return result(error.to_dict())


@admin_api.route('/api/admin/commits')
def api_commits():
    """获取Commit列表JSON"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = _normalize_filter(request.args.get('status', None))
    project_name = _normalize_filter(request.args.get('project_name', None))

    db = get_database()
    data = db.get_commit_logs_paginated(page=page, per_page=per_page, status=status, project_name=project_name)

    return jsonify({
        "items": [item.to_dict() for item in data["items"]],
        "total": data["total"],
        "page": data["page"],
        "per_page": data["per_page"],
        "pages": data["pages"]
    })


@admin_api.route('/api/admin/commits/<int:commit_id>')
def api_commit_detail(commit_id):
    """获取Commit详情JSON"""
    db = get_database()
    commit = db.get_commit_log_by_id(commit_id)
    if not commit:
        return result(None, "记录不存在", False)
    return result(commit.to_dict())


@admin_api.route('/api/admin/errors/<int:error_id>/status', methods=['POST'])
def api_update_error_status(error_id):
    """更新错误状态和上下文"""
    data = request.get_json()
    if not data or 'status' not in data:
        return result(None, "参数错误: status 必填", False)

    db = get_database()
    success = db.update_error_status(
        error_id,
        status=data['status'],
        context=data.get('context')
    )
    if success:
        return result(None, "更新成功")
    return result(None, "记录不存在", False)


@admin_api.route('/api/admin/commits/<int:commit_id>/status', methods=['POST'])
def api_update_commit_status(commit_id):
    """更新commit状态和上下文"""
    data = request.get_json()
    if not data or 'status' not in data:
        return result(None, "参数错误: status 必填", False)

    db = get_database()
    success = db.update_commit_status(
        commit_id,
        status=data['status'],
        context=data.get('context')
    )
    if success:
        return result(None, "更新成功")
    return result(None, "记录不存在", False)


# ---------- Project API ----------

@admin_api.route('/api/admin/projects')
def api_projects():
    """获取项目列表JSON"""
    db = get_database()
    projects = db.get_all_projects()
    return jsonify({"items": [p.to_dict() for p in projects]})


@admin_api.route('/api/admin/projects', methods=['POST'])
def api_add_project():
    """添加项目"""
    data = request.get_json()
    if not data or 'project_name' not in data or 'project_path' not in data:
        return result(None, "参数错误: project_name和project_path必填", False)

    # 检查是否是git仓库
    source_path = Path(data['project_path'])
    if not source_path.exists():
        return result(None, "路径不存在", False)
    git_dir = source_path / ".git"
    if not git_dir.exists():
        return result(None, "该路径不是git仓库，请先初始化git", False)

    db = get_database()
    existing = db.get_project_by_name(data['project_name'])
    if existing:
        return result(None, "项目名称已存在", False)

    project = db.insert_project(
        project_name=data['project_name'],
        project_path=data['project_path'],
        main_branch=data.get('main_branch', 'master')
    )

    # 异步设置项目
    import threading
    def setup():
        setup_project(project.id)
    threading.Thread(target=setup, daemon=True).start()

    return result(project.to_dict(), "项目已添加，正在设置工作树...")


@admin_api.route('/api/admin/projects/<int:project_id>/setup', methods=['POST'])
def api_setup_project(project_id):
    """重新设置项目"""
    success, msg = setup_project(project_id)
    if success:
        return result(None, msg)
    return result(None, msg, False)


@admin_api.route('/api/admin/projects/<int:project_id>', methods=['DELETE'])
def api_delete_project(project_id):
    """删除项目"""
    success, msg = cleanup_project(project_id)
    if success:
        return result(None, msg)
    return result(None, msg, False)


def delete_branch(project_name: str, branch_name: str) -> Tuple[bool, str]:
    """删除项目中的指定分支，只删除AI生成的分支，不删除主分支和AI工作树分支"""
    if not branch_name or not project_name:
        return True, "分支名称为空，无需删除"

    db = get_database()
    project = db.get_project_by_name(project_name)
    if not project:
        return True, "项目不存在，无需删除分支"

    try:
        # 不删除主分支
        if branch_name == project.main_branch:
            return True, "主分支不允许删除"

        # 不删除AI工作树分支
        if branch_name == config.AI_WORKTREE_BRANCH:
            return True, "AI工作树分支不允许删除"

        # 只删除AI生成的分支（ai-开头）
        if not branch_name.startswith("ai-"):
            return True, "非AI生成的分支不允许删除"

        source_path = Path(project.project_path)
        if not source_path.exists() or not (source_path / ".git").exists():
            return True, "项目不是有效的git仓库，无需删除分支"

        # 检查分支是否存在
        check_cmd = ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"]
        code, _, _ = run_command(check_cmd, cwd=str(source_path))
        if code != 0:
            return True, "分支不存在，无需删除"

        # 删除分支
        delete_cmd = ["git", "branch", "-D", branch_name]
        code, _, stderr = run_command(delete_cmd, cwd=str(source_path))
        if code != 0:
            return False, f"删除分支失败: {stderr}"

        return True, "分支删除成功"
    except Exception as e:
        log(f"删除分支失败: {e}")
        return False, str(e)


@admin_api.route('/api/admin/errors/<int:error_id>', methods=['DELETE'])
def api_delete_error(error_id):
    """删除错误记录及其关联分支"""
    db = get_database()
    error = db.get_error_log_by_id(error_id)
    if not error:
        return result(None, "记录不存在", False)

    # 如果有相关分支，尝试删除分支
    if error.branch_name and error.project_name:
        success, msg = delete_branch(error.project_name, error.branch_name)
        if not success:
            log(f"删除错误关联分支失败: {msg}")

    # 删除数据库记录
    success = db.delete_error_log(error_id)
    if success:
        return result(None, "删除成功")
    return result(None, "删除失败", False)


@admin_api.route('/api/admin/commits/<int:commit_id>', methods=['DELETE'])
def api_delete_commit(commit_id):
    """删除Commit记录及其关联分支"""
    db = get_database()
    commit = db.get_commit_log_by_id(commit_id)
    if not commit:
        return result(None, "记录不存在", False)

    # 如果有相关分支，尝试删除分支
    if commit.branch_name and commit.project_name:
        success, msg = delete_branch(commit.project_name, commit.branch_name)
        if not success:
            log(f"删除Commit关联分支失败: {msg}")

    # 删除数据库记录
    success = db.delete_commit_log(commit_id)
    if success:
        return result(None, "删除成功")
    return result(None, "删除失败", False)


@admin_api.route('/api/admin/errors/projects')
def api_error_projects():
    """获取错误列表中的项目列表"""
    db = get_database()
    projects = db.get_projects_from_errors()
    return jsonify({"projects": projects})


@admin_api.route('/api/admin/commits/projects')
def api_commit_projects():
    """获取Commit列表中的项目列表"""
    db = get_database()
    projects = db.get_projects_from_commits()
    return jsonify({"projects": projects})


@admin_api.route('/api/admin/projects/path-info', methods=['POST'])
def api_get_path_info():
    """获取路径信息：文件夹名、当前git分支"""
    data = request.get_json()
    path = data.get('path', '').strip()
    if not path:
        return result(None, "路径不能为空", False)

    source_path = Path(path)

    # 检查路径是否存在
    if not source_path.exists():
        return result(None, "路径不存在", False)

    # 获取文件夹名
    folder_name = source_path.name

    # 检查是否是git仓库
    git_dir = source_path / ".git"
    if not git_dir.exists():
        return result({
            "folder_name": folder_name,
            "current_branch": "master",
            "is_git_repo": False
        })

    # 获取当前分支
    current_branch = "master"
    branch_cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
    code, stdout, _ = run_command(branch_cmd, cwd=str(source_path))
    if code == 0 and stdout.strip():
        current_branch = stdout.strip()

    return result({
        "folder_name": folder_name,
        "current_branch": current_branch,
        "is_git_repo": True
    })
