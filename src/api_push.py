# -*- coding: utf-8 -*-
"""
推送API模块 - 接收错误日志和Git Commit信息
"""
from flask import Blueprint, request

from src import tool
from src.database import get_database
from src.tool import result, log

# 创建蓝图，URL前缀为空，保持原有接口路径不变
push_api = Blueprint('push_api', __name__, url_prefix='/api/push')


@push_api.route('error', methods=['POST'])
def push_error():
    """接收错误日志推送的HTTP接口"""
    data = request.get_json()
    if not data:
        return result(None, "参数错误", False)

    error_content = data.get('error_content', '')
    hash_content = data.get('hash_content', '')
    error_message = data.get('error_message', '')
    project_name = data.get('project_name', '')

    if not project_name:
        return result(None, "参数错误: project_name必填", False)
    if not error_content:
        return result(None, "参数错误: error_content必填", False)

    db = get_database()
    project = db.get_project_by_name(project_name)
    if not project:
        return result(None, f"项目不存在: {project_name}", False)

    log("接收错误日志推送",
        f"project_name={project_name}, error_message={error_message}, error_content={error_content[:100]}...")

    db.insert_error_log(error_content, project_name, error_message, hash_content)
    return result()


@push_api.route('commit', methods=['GET'])
def push_commit():
    """接收git commit信息推送的HTTP接口"""
    project = request.args.get('project')
    commit_id = request.args.get('commit_id')
    message = request.args.get('message')

    if not project or not commit_id:
        return result(None, "参数错误: project和commit_id必填", False)

    # 根据commit id查询commit msg
    message = tool.get_commit_message(project, commit_id)

    log("接收commit信息推送", f"project={project}, commit_id={commit_id}, message={message}")

    db = get_database()
    db.insert_commit_log(project, commit_id, message or '')
    return result()
