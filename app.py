# -*- coding: utf-8 -*-
"""
Flask应用主入口 - HTTP接口和定时器
"""
from flask import Flask, render_template
from src import scheduler
from src.api_push import push_api  # 导入API蓝图
from src.api_admin import admin_api  # 导入管理后台蓝图
from src.tool import error, log

app = Flask(__name__)

# 注册API蓝图
app.register_blueprint(push_api)
app.register_blueprint(admin_api)


@app.route('/')
def index():
    """首页 - 统计概览"""
    from src.database import get_database
    db = get_database()
    stats = db.get_stats()
    return render_template('index.html', stats=stats)


if __name__ == '__main__':
    # 启动定时器
    scheduler.start_scheduler()
    # 启动Flask服务
    app.run(host='0.0.0.0', port=3002, debug=True)
