# 前端构建阶段
FROM node:20-slim AS frontend-builder

# 设置工作目录
WORKDIR /app

# 设置npm镜像源
# RUN npm config set registry https://registry.npmmirror.com

# 安装pnpm
RUN npm install -g pnpm

# 复制前端源代码
COPY src/frontend /app

# 安装依赖并构建
RUN pnpm install --no-frozen-lockfile
RUN pnpm build

# 后端构建阶段
FROM python:3.11-slim AS backend

# 设置工作目录
WORKDIR /app

# 设置Python环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 设置apt镜像源
# RUN sed -i 's|http://deb.debian.org|https://mirrors.ustc.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt
COPY requirements.txt .

# 设置python镜像源
# RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码（排除前端目录）
COPY src /app/src
COPY . /app

# 删除前端源代码（如果有的话）
RUN rm -rf /app/src/frontend

# 创建静态文件目录
RUN mkdir -p /app/src/static_collected

# 从前端构建阶段复制编译后的文件
COPY --from=frontend-builder /app/dist/ /app/src/static_collected/

# 暴露端口
EXPOSE 8000

# 设置启动命令
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "src.backend.sitesearch.conf.asgi:application"]
