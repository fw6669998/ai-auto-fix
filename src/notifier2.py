import asyncio
import threading
from aibot import WSClient, WSClientOptions, generate_req_id
from flask import Flask, request, jsonify

# 1. 创建客户端实例
ws_client = WSClient(
    WSClientOptions(
        bot_id='aibVO8ISDfowMIHTEuwpIZFYcLH6DdygGGK',  # 企业微信后台获取的机器人 ID
        secret='PzgoPA8gETsSwnQcDaz64JuM2nnJyhpd0Y745naLKh4',  # 企业微信后台获取的机器人 Secret
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


# 6. Flask HTTP 服务
app = Flask(__name__)
loop = None


# 固定消息配置
FIXED_MESSAGES = {
    'alert': '⚠️ 系统告警，请及时处理',
    'info': 'ℹ️ 系统通知',
    'success': '✅ 操作成功',
    'error': '❌ 操作失败',
}


@app.route('/send', methods=['GET'])
def send_message():
    """接收 HTTP GET 请求，通过消息标识发送固定消息"""
    try:
        msg_id = request.args.get('msg_id', '')
        user_id = request.args.get('user_id', '17320394612')

        if not msg_id:
            return jsonify({'status': 'error', 'message': 'msg_id is required'}), 400

        content = FIXED_MESSAGES.get(msg_id)
        if not content:
            return jsonify({'status': 'error', 'message': f'unknown msg_id: {msg_id}'}), 400

        # 构建消息体
        body = {
            'msgtype': 'text',
            'text': {'content': content}
        }

        # 在事件循环中运行异步发送
        asyncio.run_coroutine_threadsafe(
            ws_client.send_message(user_id, body),
            loop
        )
        return jsonify({'status': 'success', 'message': 'message sent'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def start_flask():
    """启动 Flask 服务器（在单独线程中）"""
    app.run(host='0.0.0.0', port=8080, use_reloader=False)


# 7. 启动
if __name__ == '__main__':
    # 创建并设置事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 在后台线程启动 Flask
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    print('HTTP 服务已启动: http://0.0.0.0:8080/send')

    # 启动 WebSocket 客户端
    ws_client.run()
