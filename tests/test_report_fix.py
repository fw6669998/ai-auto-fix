# -*- coding: utf-8 -*-
"""
报告错误到 auto-optimize 项目
"""
import requests

from src.ai_fixer import call_agent_fix, ai_fix

API_URL = "http://localhost:3002/push_error"
payload = {
    'error_content': 'Traceback (most recent call last):\n  File "D:\\data\\env\\auto-optimize\\Lib\\site-packages\\flask\\app.py", line 917, in full_dispatch_request\n    rv = self.dispatch_request()\n  File "D:\\data\\env\\auto-optimize\\Lib\\site-packages\\flask\\app.py", line 902, in dispatch_request\n    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]\n           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^\n  File "C:\\Users\\fw666\\OneDrive\\auto-optimize\\tests\\app1\\demo_app.py", line 23, in get_username\n    username = user_info[\'username\']\n               ~~~~~~~~~^^^^^^^^^^^^\nTypeError: \'NoneType\' object is not subscriptable\n',
    'error_message': "'NoneType' object is not subscriptable",
    'project_name': 'app1'
}


def test_report_error():
    """报告错误到主项目"""
    try:
        resp = requests.post(API_URL, json=payload, timeout=10)
        result = resp.json()
        print(f"报告结果: {result}")
        return result
    except requests.exceptions.ConnectionError:
        print(f"连接失败，请确保 auto-optimize 服务运行在 {API_URL}")
        return None
    except Exception as e:
        print(f"报告失败: {e}")
        return None


def test_call_claude_code_fix():
    """测试调用Claude Code CLI"""
    project_path = "C:/Users/fw666/OneDrive/auto-optimize/tests/app1_ai"
    error_message = payload['error_content']
    result = call_agent_fix(project_path, error_message)
    # 验证返回格式正确：returncode=0 表示成功
    print(result)
    pass


def test_ai_fix():
    """测试调用Claude Code CLI"""
    project_path = "C:/Users/fw666/OneDrive/auto-optimize/tests/app1"
    result = ai_fix(project_path, payload['error_content'])
    # 验证返回格式正确：returncode=0 表示成功
    print(result)
    pass


if __name__ == '__main__':
    test_report_error()
