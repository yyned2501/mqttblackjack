# 标准库
import time as time_module
from datetime import time as time_class
from datetime import datetime
import json, asyncio, random

# 第三方库
import aiomqtt
from aiomqtt import MqttError, Message


# 自定义
from libs.game import do_game, game_state, get_gamelist
from libs.mqtt import Client
from libs.log import logger
from libs.toml import config


HELP_TOPIC = "blackjack/help"
GAME_TOPIC = "blackjack/games"
STATE_TOPIC = "blackjack/states"
g = {}
friends = (99872, 99785, 100727)
lock = asyncio.Lock()


def is_within_time_ranges(time_ranges):
    now = datetime.now().time()
    for start_str, end_str in time_ranges:
        start = time_class.fromisoformat(start_str)
        end = time_class.fromisoformat(end_str)
        if start <= now <= end:
            return True
    return False


async def help_queue(client: Client, message: Message):
    data = json.loads(message.payload)
    userid = data["userid"]
    if not userid == g["MDID"]:
        logger.info(f"好友{data["userid"]}需要帮助，已添加至列队。")
        g["help_queue"][data["userid"]] = data


async def done_queue(client: Client, message: Message):
    userid = message.payload.decode()
    if userid == g["MDID"]:
        pass
    else:
        logger.info(f"好友{userid}已获得帮助，从列队中移除。")
        del g["help_queue"][userid]


async def play():
    while True:
        g["auto_time"] = is_within_time_ranges(config.get("GAME.AFK.TIME"))
        g["natural_time"] = is_within_time_ranges(config.get("GAME.NATURAL.TIME"))
        if g["auto_time"] or g["natural_time"]:
            pass
        else:
            await asyncio.sleep(10)


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
    g["help_queue"] = {}
    g["next_start_time"] = datetime.now().time()
    if g["MDID"] not in friends:
        logger.error("非授权用户，请联系管理员")
        return
    client = Client(
        config.get("MQTT.HOST"),
        username=config.get("MQTT.USER"),
        password=config.get("MQTT.PASSWORD"),
        identifier=f"{g["MDID"]}_{hash(time_module.time())}",
    )
    interval = 5

    while True:
        try:
            async with client:
                await client.subscribe(HELP_TOPIC)
                await client.subscribe(GAME_TOPIC)
                await asyncio.gather(listen(client), start_game(client), play_game())
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
