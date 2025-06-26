docker-compose.yml
```docker-compose.yml
services:
  blackjack:
    image: yyned2501/git-python
    container_name: blackjack
    volumes:
      - ./config:/app/config
    environment:
      - TZ=Asia/Shanghai
      - GIT_REMOTE=https://github.com/yyned2501/mqttblackjack.git
      - GIT_BRANCH=master
      - SUPERVISOR_USERNAME=admin
      - SUPERVISOR_PASSWORD=admin
    network_mode: bridge
    working_dir: /app
    ports:
      - 9001:9001 #supervisor管理端口
    tty: true
```
编辑config.toml 后重启docker


