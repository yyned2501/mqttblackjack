ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}

# 设置工作目录
WORKDIR /app

# 复制应用文件和入口脚本
COPY requirements.txt packages.txt ./
COPY docker-entrypoint.sh supervisord.conf ./

# 安装系统依赖和Python包
RUN apt-get update && \
    apt-get install -y git && \
    xargs -a packages.txt apt-get install -y --no-install-recommends && \
    apt-get clean && \
    fc-cache -f -v && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*; 

RUN pip install --upgrade pip -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com && \
    pip install supervisor -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com

RUN pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com;

# 运行入口脚本
CMD ["bash", "docker-entrypoint.sh"]