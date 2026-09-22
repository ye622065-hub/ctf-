FROM python:3.11-slim

WORKDIR /app

# 依赖在镜像构建期安装，不要放到容器启动命令里
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 拷贝题目源码（compose 中同时挂载 ./app，方便随时修改热生效）
COPY app/ /app/

EXPOSE 5000

# 容器内固定通过服务名 db:3306 连数据库，启动前由 Python 自行重试等待
CMD ["python", "app.py"]
