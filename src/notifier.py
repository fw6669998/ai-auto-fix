"""
企业微信通知模块 - 集成到主服务中
"""
import asyncio
import threading
from typing import Optional
from flask import Blueprint, request
from aibot import WSClient, WSClientOptions

from . import config
from .tool import log, result

# 创建蓝图
notifier_api = Blueprint('notifier_api', __name__, url_prefix='/api/notifier')

# 全局实例
_ws_client: Optional[WSClient] = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_running = False


class _QuietAiBotLogger:
    """屏蔽 SDK 的 DEBUG 日志，避免心跳日志刷屏。"""

    def debug(self, message: str, *args: object) -> None:
        # log(f'AiBotSDK debug: {message}', *args)
        pass

    def info(self, message: str, *args: object) -> None:
        log(f'AiBotSDK info: {message}', *args)

    def warn(self, message: str, *args: object) -> None:
        log(f'AiBotSDK warn: {message}', *args)

    def error(self, message: str, *args: object) -> None:
        log(f'AiBotSDK error: {message}', *args)


@notifier_api.route('send', methods=['POST'])
def send_message():
    """发送企业微信消息的HTTP接口"""
    data = request.get_json(force=True, silent=True)
    content = data.get('content')
    if not content:
        return result(None, "参数错误: content必填", False)

    success = send_message_sync(content)
    if success:
        return result(None, "消息发送成功")
    else:
        return result(None, "消息发送失败", False)


def init_notifier():
    """初始化企业微信通知客户端"""
    global _ws_client, _loop, _running

    if _running:
        return

    _ws_client = WSClient(
        WSClientOptions(
            bot_id=config.NOTIFIER_BOT_ID,
            secret=config.NOTIFIER_SECRET,
            logger=_QuietAiBotLogger(),
        )
    )

    @_ws_client.on('authenticated')
    def on_authenticated():
        global _loop
        _loop = asyncio.get_running_loop()

    @_ws_client.on('disconnected')
    def on_disconnected():
        pass

    @_ws_client.on('error')
    def on_error(error):
        log(f'❌ 企业微信通知客户端错误: {error}')

    @_ws_client.on('message.text')
    async def on_text(frame):
        pass

    @_ws_client.on('event.enter_chat')
    async def on_enter_chat(frame):
        await _ws_client.reply_welcome(frame, {
            'msgtype': 'text',
            'text': {'content': '您好！我是AI助手通知机器人，修复和审查结果将在此通知。'},
        })

    def run_websocket():
        global _loop, _running
        loop = asyncio.new_event_loop()
        _loop = loop
        asyncio.set_event_loop(loop)
        try:
            async def connect_client():
                await _ws_client.connect()

            loop.run_until_complete(connect_client())
            loop.run_forever()
        except Exception as e:
            log(f'WebSocket 线程异常: {type(e).__name__}, {e}')
            import traceback
            log(traceback.format_exc())
        finally:
            _running = False
            if not loop.is_closed():
                loop.close()

    thread = threading.Thread(target=run_websocket, daemon=True)
    thread.start()
    _running = True


def send_message_sync(content: str):
    """同步发送消息（供非异步代码调用）"""
    print('发送消息通知')
    user_id = config.NOTIFIER_USER_ID
    loop = _loop
    if not _ws_client or not loop:
        log('企业微信通知客户端未初始化')
        return False

    if loop.is_closed() or not loop.is_running():
        log(f'企业微信通知事件循环不可用, is_running={loop.is_running()}, is_closed={loop.is_closed()}')
        return False

    try:
        body = {
            'msgtype': 'markdown',
            'markdown': {'content': content}
        }

        async def do_send():
            try:
                await _ws_client.send_message(user_id, body)
            except Exception as e:
                log(f'企业微信消息发送异常: {type(e).__name__}, {e}')
                import traceback
                log(traceback.format_exc())

        future = asyncio.run_coroutine_threadsafe(do_send(), loop)

        def on_done(done_future):
            try:
                done_future.result()
            except Exception as e:
                log(f'消息发送任务异常: {type(e).__name__}, {e}')

        future.add_done_callback(on_done)
        return True
    except Exception as e:
        log(f'发送企业微信消息失败:{type(e).__name__}, {e}')
        import traceback
        log(traceback.format_exc())
        return False


def notify_error_fixed(
        error_id: int,
        project_name: str,
        error_message: str,
        status: str,
        branch_name: str = None,
        how_fix: str = '',
        cause: str = '',
):
    """发送错误修复结果通知"""
    if status == 'success':
        status_text = '修复成功'
    elif status == 'failure':
        status_text = '修复失败'
    else:
        status_text = '已跳过'

    content = f"""**错误修复结果**
**项目**: {project_name}
**状态**: {status_text}
**错误信息**: {error_message}
**造成原因**: {cause}
**修复方法**: {how_fix}
**分支**: {branch_name}
**详情衔接**: [点击查看]({config.BASE_URL}/admin/errors/{error_id})
"""
    return send_message_sync(content)


def notify_commit_reviewed(
        commit_id: int,
        project_name: str,
        commit_message: str,
        status: str,
        branch_name: str = None,
        issue: str = '',
        how_fix: str = '',
):
    """发送Commit审查结果通知"""
    if status == 'no_issue':
        status_text = '没有发现问题'
    elif status == 'has_issue':
        status_text = '发现问题并已修复'
    else:
        status_text = '检查失败'

    content = f"""**Commit审查结果**
**项目**: {project_name}
**提交消息**: {commit_message[:100]}
**状态**: {status_text}
**问题**: {issue}
**修复方法**: {how_fix}
**修复分支**: {branch_name}
**详情衔接**: [点击查看]({config.BASE_URL}/admin/commits/{commit_id})
"""
    return send_message_sync(content)
