# 湖州师范大学校园失物招领系统 —— Dockerfile
FROM python:3.11-slim

# 基础环境
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# ====== 换国内镜像源（清华）======
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
    || sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list 2>/dev/null \
    || true

# 安装系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 先复制依赖描述，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY app.py .
COPY templates ./templates
COPY init.sh .

# 数据持久化目录（SQLite DB 存在这里）
VOLUME ["/app/instance"]

# 容器启动时执行 init.sh，会自动初始化数据库并启动 gunicorn
RUN chmod +x init.sh
EXPOSE 5000

CMD ["./init.sh"]
