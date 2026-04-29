import asyncio
import os
import sqlite3
from dotenv import load_dotenv
from aibot import WSClient, WSClientOptions, generate_req_id

from src import tool

# 加载 .env 文件中的环境变量
load_dotenv()

# 数据库路径
conn = tool.get_db()

# 1. 创建客户端实例
ws_client = WSClient(
    WSClientOptions(
        bot_id='aibNQlFp9lV1Lnce1X8YtSNw7nTVdmdzYfr',  # 企业微信后台获取的机器人 ID
        secret='yOMgsSxxhtYS1p3mN7aYYgJCzPxGHcGnyBtcRm6QOMR',  # 企业微信后台获取的机器人 Secret
    )
)


# 2. 监听认证成功
@ws_client.on('authenticated')
def on_authenticated():
    print('🔐 认证成功')
    # 认证成功后启动错误日志处理任务
    asyncio.create_task(process_error_logs())


# 3. 监听文本消息并进行流式回复
@ws_client.on('message.text')
async def on_text(frame):
    content = frame.get('body', {}).get('text', {}).get('content', '')
    print(f'收到文本: {content}')

    stream_id = generate_req_id('stream')

    # 发送流式中间内容
    await ws_client.reply_stream(frame, stream_id, '正在思考中...', False)

    # 发送最终结果
    await asyncio.sleep(1)
    await ws_client.reply_stream(frame, stream_id, f'你好！你说的是: "{content}"', True)


# 4. 监听进入会话事件（发送欢迎语）
@ws_client.on('event.enter_chat')
async def on_enter_chat(frame):
    await ws_client.reply_welcome(frame, {
        'msgtype': 'text',
        'text': {'content': '您好！我是智能助手，有什么可以帮您的吗？'},
    })


# 5. 处理错误日志表的任务
async def process_error_logs():
    """每20秒遍历一次错误日志表，发送状态为0的消息"""
    while True:
        try:
            await asyncio.sleep(20)  # 每20秒执行一次
            await send_pending_error_messages()
        except Exception as e:
            print(f'处理错误日志时发生异常: {e}')


async def send_pending_error_messages():
    """查询并发送待处理的错误消息"""
    try:
        cursor = conn.cursor()

        # 查询发送状态为0的错误消息
        cursor.execute('SELECT id, error_content FROM error_logs WHERE send_status = 0 or send_status IS NULL')
        pending_messages = cursor.fetchall()

        if not pending_messages:
            print('没有待发送的错误消息')
            conn.close()
            return

        for msg_id, message in pending_messages:
            try:
                # 发送 markdown 格式消息
                body = {
                    'msgtype': 'markdown',
                    'markdown': {'content': message}
                }
                await ws_client.send_message('17320394612', body)
                print(f'已发送错误消息 [{msg_id}]: {message[:50]}...')

                # 发送成功后修改状态为1
                cursor.execute('UPDATE error_logs SET send_status = 1 WHERE id = ?', (msg_id,))
                conn.commit()
            except Exception as e:
                print(f'发送消息 [{msg_id}] 失败: {e}')
                continue

    except Exception as e:
        print(f'查询错误日志失败: {e}')


# 6. 启动（便捷方法，内部管理事件循环）
if __name__ == '__main__':
    ws_client.run()
