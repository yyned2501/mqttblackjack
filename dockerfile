# 基础镜像阶段 - 安装系统依赖和Python包
ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION} AS base

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 安装Python基础依赖
RUN pip install --upgrade pip -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com && \
    pip install supervisor -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com

# 依赖安装阶段 - 安装requirements.txt
FROM base AS dependencies
WORKDIR /app
COPY requirements.txt packages.txt ./
RUN apt-get update && \
    xargs -a packages.txt apt-get install -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com && \
    python -c "import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro, sep='.')" > /python_version.txt

# 最终镜像阶段
FROM base
WORKDIR /app
COPY --from=dependencies /python_version.txt .
RUN PYTHON_FULL_VERSION=$$(cat /python_version.txt) && \
    mkdir -p /usr/local/lib/python$${PYTHON_FULL_VERSION}/site-packages && \
    cp -r /usr/local/lib/python$${PYTHON_FULL_VERSION}/site-packages /usr/local/lib/python${PYTHON_VERSION}/ && \
    rm /python_version.txt

COPY --from=dependencies /usr/local/bin /usr/local/bin
COPY docker-entrypoint.sh supervisord.conf ./
RUN git config --global --add safe.directory /app
CMD ["bash", "docker-entrypoint.sh"]