import threading
import time

import config
from src import database, ai_fixer, ai_reviewer
from src.tool import log
from src.model import ErrorLog

# 全局服务实例
scheduler_thread = None
scheduler_running = False


class SchedulerThread(threading.Thread):
    """定时器线程"""

    def __init__(self, interval: int = None):
        super().__init__()
        self.interval = interval or config.FETCH_INTERVAL_SECONDS
        self.db = database.get_database()
        self.running = False

    def run(self):
        global scheduler_running
        scheduler_running = True

        while self.running:
            try:
                with threading.Lock():
                    ai_fixer.process_errors()
                    ai_reviewer.process_commits()


            except Exception as e:
                log(f"定时任务执行错误:", e.__class__.__name__, {e})
            # 计算下次执行时间
            time.sleep(self.interval)

    def stop(self):
        self.running = False
        global scheduler_running
        scheduler_running = False


def start_scheduler(interval: int = None):
    """启动定时器"""
    global scheduler_thread, scheduler_running

    if scheduler_running:
        return

    scheduler_thread = SchedulerThread(interval)
    scheduler_thread.running = True
    scheduler_thread.start()


def stop_scheduler():
    """停止定时器"""
    global scheduler_thread, scheduler_running

    if scheduler_thread:
        scheduler_thread.running = False
        scheduler_thread.join()
        scheduler_running = False



