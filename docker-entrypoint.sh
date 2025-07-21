#!/bin/bash

# 安装Python包函数
install_pip_package() {
    local package=$1
    echo "安装Python包: $package"
    pip install "$package" -i http://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host=mirrors.aliyun.com --upgrade >/dev/null 2>&1
}

# Git仓库操作函数
setup_git_repo() {
    # 设置默认分支
    if [ -z "$GIT_BRANCH" ]; then
        echo "GIT_BRANCH 未设置，使用默认值 master"
        GIT_BRANCH="master"
    fi

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

# 主执行流程
if [ -n "$GIT_REMOTE" ]; then
    setup_git_repo
fi

# 更新pip并安装必要包
install_pip_package pip
install_pip_package supervisor

if [ -f "requirements.txt" ]; then
    echo "安装项目依赖"
    pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host=mirrors.aliyun.com --upgrade >/dev/null 2>&1
fi

echo "启动 supervisord"
supervisord -c supervisord.conf -n