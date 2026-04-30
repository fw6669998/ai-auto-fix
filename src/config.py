import os

# 数据库连接字符串，使用SQLite数据库存储日志和任务数据
DATABASE_CONFIG = "sqlite:///data/logs.db"

# AI工作分支名称，用于创建临时的AI操作分支
AI_WORKTREE_BRANCH = "ai-worktree"
# AI工作树根目录路径，用于存放各个项目的AI工作副本
AI_WORKTREES_PATH = r"D:\project\ai_worktrees"

# 处理代码任务的agent命令，使用Claude Code执行AI代理任务
# {prompt} 占位符会被替换为实际的任务提示词
AGENT_COMMAND = ["claude", "--dangerously-skip-permissions", "-p", '{prompt}']

# 调度器轮询间隔（秒），每隔多少秒检查并处理待处理的任务
FETCH_INTERVAL_SECONDS = 60

# 管理后台的基础URL地址，用于生成通知链接等
BASE_URL = os.getenv("BASE_URL", "http://localhost:3002")

# 企业微信机器人配置，用于推送通知消息
NOTIFIER_BOT_ID = os.getenv("NOTIFIER_BOT_ID")
NOTIFIER_SECRET = os.getenv("NOTIFIER_SECRET")
NOTIFIER_USER_ID = os.getenv("NOTIFIER_USER_ID")
