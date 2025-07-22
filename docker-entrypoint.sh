#!/bin/bash
GIT_BRANCH="master"
GIT_REMOTE="https://github.com/yyned2501/mqttblackjack.git"
# 安装Python包函数
install_pip_package() {
    local package=$1
    echo "安装Python包: $package"
    pip install "$package" -i http://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host=mirrors.aliyun.com --upgrade >/dev/null 2>&1
}

# Git仓库操作函数
setup_git_repo() {
    # 初始化Git仓库（如果不存在）
    if [ ! -d ".git" ]; then
        echo "初始化Git仓库"
        git config --global --add safe.directory /app
        git init
        git remote add origin "$GIT_REMOTE"
        git fetch origin >/dev/null
    fi

    # 拉取最新代码
    echo "更新Git仓库"
    git reset --hard origin/"$GIT_BRANCH"
    git pull origin "$GIT_BRANCH"
}

# 安装系统依赖
install_system_packages() {
    echo "安装系统依赖"
    apt-get update >/dev/null
    xargs -a packages.txt apt-get install -y --no-install-recommends >/dev/null 2>&1
    fc-cache -f -v
    apt-get clean
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
}


setup_git_repo

echo "创建目录"
mkdir -p logs
mkdir -p temp_file

echo "启动 supervisord"
supervisord -c supervisord.conf -n