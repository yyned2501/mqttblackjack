# 标准库
import datetime
import time
import json
import asyncio
import random

# 第三方库
import aiomqtt
from aiomqtt import MqttError, Message


# 自定义
from libs.game_new import do_game, game_state, get_gamelist
from libs.mqtt import Client
from libs.log import logger
from libs.toml import config
from libs.g import g

HELP_TOPIC = "blackjack/help"
GAME_TOPIC = "blackjack/games"
STATE_TOPIC = "blackjack/states"
friends = (99872, 99785, 100727, 101745)
lock = asyncio.Lock()


async def get_my_id():
    pass


async def start_game(client: Client):
    pass


def is_within_time_ranges(time_ranges):
    """检查当前时间是否在任意一个时间范围内(支持跨天时间段)"""
    now = datetime.datetime.now()
    current_time = now.time()

    for start_str, end_str in time_ranges:
        start = datetime.time.fromisoformat(start_str)
        end = datetime.time.fromisoformat(end_str)

        # 处理跨天时间段(如23:00-01:00)
        if end < start:
            # 当前时间在开始时间之后(当天)或结束时间之前(次日)
            if current_time >= start or current_time <= end:
                return True
        else:
            # 正常时间段
            if start <= current_time <= end:
                return True

    return False


def get_next_time_delta(time_ranges):
    """计算当前时间到下一个最近有效时间段开始的时间差(秒数)"""
    now = datetime.datetime.now()
    current_timestamp = now.timestamp()

    # 收集所有未来的时间戳
    timestamps = []
    for start_str, _ in time_ranges:
        start_time = datetime.time.fromisoformat(start_str)
        # 创建今天的开始时间
        start_datetime = datetime.datetime.combine(now.date(), start_time)
        start_timestamp = start_datetime.timestamp()

        # 如果今天的时间已过，使用明天的同一时间
        if start_timestamp <= current_timestamp:
            start_timestamp += 86400  # 增加1天(24*60*60秒)

        timestamps.append(start_timestamp)

    # 排序时间戳
    timestamps.sort()

    # 找到第一个大于当前时间的时间戳
    for ts in timestamps:
        if ts > current_timestamp:
            return ts - current_timestamp

    # 如果没有找到(理论上不会发生)，返回默认值
    return 10


async def help_queue(client: Client, message: Message):
    data = json.loads(message.payload)
    if "userid" in data:
        userid = data["userid"]
        if not userid == g["MDID"]:
            logger.info(f"好友{data["userid"]}需要帮助，已添加至列队。")
            g["help_queue"].add(userid)


async def done_queue(client: Client, message: Message):
    userid = message.payload.decode()
    if userid == g["MDID"]:
        sleep = config.get("GAME.GLOBAL.SLEEP", 10) / 4
        g["next_start_time"] = int(
            time.time() + max(sleep * random.uniform(0.75, 1.25), 20)
        )
        logger.info(f"好友开始帮助，缩减下次开局时间。")
    else:
        logger.info(f"好友{userid}已获得帮助，从列队中移除。")
        g["help_queue"].discard(userid)


async def help_friend(client: Client):
    pass


async def open(client: Client):
    while True:
        g["auto_time"] = is_within_time_ranges(config.get("GAME.AFK.TIME"))
        g["natural_time"] = is_within_time_ranges(config.get("GAME.NATURAL.TIME"))
        if g["auto_time"] or g["natural_time"]:
            if time.time() >= g["next_start_time"]:
                await start_game(client)
                g["next_start_time"] = int(
                    time.time()
                    + config.get("GAME.GLOBAL.SLEEP") * random.uniform(0.75, 1.25)
                )
            sleep_time = max(int(g["next_start_time"] - time.time()), 1)
            await asyncio.sleep(sleep_time)
        else:
            # 合并两个时间段配置
            time_ranges = config.get("GAME.AFK.TIME") + config.get("GAME.NATURAL.TIME")
            delta = get_next_time_delta(time_ranges)
            sleep_time = max(delta / 2, 10) if delta else 10
            await asyncio.sleep(sleep_time)


async def play(client: Client):
    async with lock:
        if g["help_queue"]:
            userid = g["help_queue"].pop()
            client.publish(GAME_TOPIC, userid)
            logger.info(f"开始帮助好友{userid}")
            await get_gamelist()
            if userid not in g["game_list"]:
                logger.info(f"帮助好友{userid}失败，被人抢了")
                return
            await help_friend()


async def listen(client: Client):
    while True:
        try:
            async for message in client.messages:
                if message.topic.matches(HELP_TOPIC):
                    await help_queue(client, message)
                if message.topic.matches(GAME_TOPIC):
                    await done_queue(client, message)
                else:
                    logger.warning(f"未知主题{message.topic}")
        except MqttError as ee:
            logger.error("MQTT异常，尝试重新连接: %s", ee, exc_info=True)
            raise
        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}", exc_info=True)
            await asyncio.sleep(10)


async def main():
    g["MDID"] = await get_my_id()
    g["next_start_time"] = time.time()
    if g["MDID"] not in friends:
        logger.error("非授权用户，请联系管理员")
        return
    client = Client(
        config.get("MQTT.HOST"),
        username=config.get("MQTT.USER"),
        password=config.get("MQTT.PASSWORD"),
        identifier=f"{g["MDID"]}_script",
    )
    interval = 5

    while True:
        try:
            async with client:
                await client.subscribe(HELP_TOPIC)
                await client.subscribe(GAME_TOPIC)
                await asyncio.gather(listen(client), start_game(client), open())
        except MqttError:
            logger.error(f"Connection lost; Reconnecting in {interval} seconds ...")
            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(e, exc_info=True)
        finally:
            tasks = asyncio.all_tasks() - {asyncio.current_task()}
            for task in tasks:
                task.cancel()
                try:
                    await task
                except Exception as e:
                    logger.error(f"Error while cancelling task: {e}")


if __name__ == "__main__":
    asyncio.run(main())
