import logging
import os
import traceback
import threading
import requests
from flask import jsonify
from werkzeug.exceptions import HTTPException
from pathlib import Path

PROJECT_PATH = str(Path(__file__).resolve().parent) + os.sep  # 项目根目录

API_URL = "http://192.168.1.100:3002/api/push/error"


class ExpectException(Exception):
    """自定义异常"""
    pass


class PasswordError(ExpectException):
    """密码错误异常"""
    pass


def handle_exception(e):
    """全局异常处理"""
    # 预期异常, HTTP 异常（如 404）保持原始状态码，不作为服务器内部错误处理
    if isinstance(e, ExpectException) or isinstance(e, HTTPException):
        return jsonify({
            "data": None,
            "success": False,
            "message": str(e)
        }), e.code
    traceback_str = traceback.format_exc()
    traceback_str = traceback_str.replace(PROJECT_PATH, "")  # 替换项目根目录,以防在原项目上修改
    payload = {
        "error_content": traceback_str,
        "error_message": str(e),
        "project_name": "app1"
    }
    logging.error(f"报告错误: {payload}")

    def send_report(p):
        try:
            requests.post(API_URL, json=p, timeout=3)
        except Exception as e2:
            logging.error(f"报告失败: {e2}")

    threading.Thread(target=send_report, args=(payload,), daemon=True).start()
    # 返回统一的错误响应
    return jsonify({
        "data": None,
        "success": False,
        "message": f"internal server error,{str(e)}"
    }), 500
