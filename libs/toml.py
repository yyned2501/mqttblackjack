import os
import tomllib


def read(file_path) -> dict:
    """读取 toml 文件"""
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "rb") as f:
        return tomllib.load(f)


class Config:
    def __init__(self, path):
        self.config = read(path)

    def get(self, key: str, default=None):
        """获取配置值，支持任意层级的点分路径，不区分大小写"""
        if not self.config or not key:
            return default

        keys = key.lower().split(".")
        current = self.config

        for k in keys:
            if not isinstance(current, dict):
                return default

            # 在当前层级查找不区分大小写的匹配
            matched = None
            for actual_key in current.keys():
                if actual_key.lower() == k:
                    matched = actual_key
                    break

            if matched is None:
                return default

            current = current[matched]

        return current


if __name__ == "__main__":
    config = Config("config/config_new.toml")
    print(config.get("GAME.AFK.bonus", 0))
