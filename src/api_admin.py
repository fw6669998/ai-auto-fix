# -*- coding: utf-8 -*-
"""
管理后台API模块 - 页面路由和数据接口
"""
import os
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify
from src.database import get_database
from src.tool import result, log, run_command
from src.project_manager import setup_project, cleanup_project

admin_api = Blueprint('admin_api', __name__, url_prefix='/')


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
    status = request.args.get('status', None)
    return render_template('errors.html', page=page, status=status)


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
    status = request.args.get('status', None)
    return render_template('commits.html', page=page, status=status)


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
    status = request.args.get('status', None)

    db = get_database()
    data = db.get_error_logs_paginated(page=page, per_page=per_page, status=status)

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
    status = request.args.get('status', None)

    db = get_database()
    data = db.get_commit_logs_paginated(page=page, per_page=per_page, status=status)

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
    if not data or 'fix_result' not in data:
        return result(None, "参数错误: fix_result 必填", False)

    db = get_database()
    success = db.update_error_status(
        error_id,
        fix_result=data['fix_result'],
        context=data.get('context')
    )
    if success:
        return result(None, "更新成功")
    return result(None, "记录不存在", False)


@admin_api.route('/api/admin/commits/<int:commit_id>/status', methods=['POST'])
def api_update_commit_status(commit_id):
    """更新commit状态和上下文"""
    data = request.get_json()
    if not data or 'check_result' not in data:
        return result(None, "参数错误: check_result 必填", False)

    db = get_database()
    success = db.update_commit_status(
        commit_id,
        check_result=data['check_result'],
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

