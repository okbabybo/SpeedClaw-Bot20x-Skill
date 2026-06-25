# SpeedClaw BotKing v1.4.3 - Docker镜像
# 现货网格+趋势双引擎量化机器人

FROM python:3.11-slim

LABEL maintainer="okbabybo <@Okbabybo>"
LABEL version="1.4.3"
LABEL description="SpeedClaw BotKing 现货量化机器人"

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY bot/ ./bot/
COPY scripts/ ./scripts/

# 默认命令
CMD ["python3", "bot/bot_king.py"]