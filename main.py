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
from libs.toml import read

HELP_TOPIC = "blackjack/help"
GAME_TOPIC = "blackjack/games"
time_ranges = [
    ("00:01", "00:35"),
    ("08:00", "11:00"),
    ("12:00", "15:00"),
    ("16:00", "18:00"),
    ("19:30", "21:30"),
    ("22:30", "23:50"),
]

config = read("config/config.toml")
MYID = config["BASIC"].get(
    "MYID",
    config["GAME"].get("MYID", 0),
)
HOST = config["BASIC"]["HOST"]
MQTT_USER = config["BASIC"]["MQTT_USER"]
MQTT_PASSWORD = config["BASIC"]["MQTT_PASSWORD"]

if MYID == 0:
    logger.error("未获取到用户id，不自动开局")

lock = asyncio.Lock()
g = {}
friends = (99872, 99785, 100727)
bonus = config["GAME"].get("bonus", 100)
if bonus not in [100, 1000, 10000, 100000]:
    logger.warning("挂机魔力设置不在列表内，自动设置为100")
    bonus = 100
# 读取保留点数，默认值18
remain_point = config["GAME"].get("remain_point", 18)
# 读取自助模式，默认值false
gift_model = config["GAME"].get("gift_model", False)
gift_remain_point = config["GAME"].get("gift_remain_point", 20)
gift_bonus = config["GAME"].get("gift_bonus", 100)
if gift_bonus not in [100, 1000, 10000, 100000]:
    logger.warning("自助魔力设置不在列表内，自动设置为100")
    gift_bonus = 100
natural_remain_point = config["GAME"].get("natural_remain_point", 16)
natural_bonus = config["GAME"].get("natural_bonus", 100)
if natural_bonus not in [100, 1000, 10000, 100000]:
    logger.warning("自然魔力设置不在列表内，自动设置为100")
    natural_bonus = 100
boom_rate = config["GAME"].get("boom_rate", 0)
win_rate = config["GAME"].get("win_rate", 0.58)
auto_time = config["GAME"].get("auto_time", time_ranges)
natural_mode_time = config["GAME"].get("natural_mode_time", [])
sleep = config["GAME"].get("sleep", 60)
auto_play = config["GAME"].get("auto_play", False)
play_point = config["GAME"].get("play_point", 100)
play_sleep = config["GAME"].get("play_sleep", 60)
play_time = auto_time + natural_mode_time


async def help(client: Client, message: Message):
    async with lock:
        data = json.loads(message.payload)
        userid = data["userid"]
        if not (userid == MYID):
            boom_data = {
                "game": "hit",
                "start": "yes",
                "userid": userid,
                "amount": data["amount"],
            }
            logger.info(f"队友[{userid}]需要帮助，开始帮助队友平局")
            if await do_game(boom_data, 21, "平局"):
                await client.publish(
                    GAME_TOPIC,
                    payload=json.dumps(userid),
                )
        else:
            logger.debug("自己的消息，不平局")


async def start_my_game(client: Client, games: list[int] = []):
    if len(set(games) & set(friends)) >= 2:
        logger.info("已有两个队友挂机，取消开局")
        return
    async with lock:
        # 设置挂机数为默认值
        run_gift_model = gift_model
        run_amount = bonus
        run_remain_point = remain_point
        # 计算本局是否自助
        boom = random.random() < boom_rate
        if g["win_rate"] > win_rate:
            logger.info(f"当前胜率{g["win_rate"]}超过{win_rate},自动开启自助")
            run_gift_model = True
        if run_gift_model:
            run_remain_point = gift_remain_point
            run_amount = gift_bonus
        elif g["natural_time"]:  # 是否自然下注时间
            run_remain_point = natural_remain_point
            run_amount = natural_bonus
        start_data = {
            "game": "hit",
            "start": "yes",
            "amount": run_amount,
        }
        point = await do_game(start_data, run_remain_point, "开局")
        logger.info(f"开局{run_amount}魔力，点数{point}")
        if point and point > 21:
            if not (g["natural_time"] or gift_model or boom):
                logger.info(f"寻求队友平局")
                await client.publish(
                    HELP_TOPIC,
                    payload=json.dumps(
                        {
                            "userid": MYID,
                            "amount": run_amount,
                            "point": point,
                        }
                    ),
                )


async def listen(client: Client):
    sleep = config["GAME"].get("sleep", 60)
    quick_sleep = int(sleep / 3)
    while True:
        try:
            async for message in client.messages:
                if message.topic.matches(HELP_TOPIC):
                    await help(client, message)
                elif message.topic.matches(GAME_TOPIC) and MYID > 0:
                    if message.payload.decode() == str(MYID):
                        sleeptime = random.randint(quick_sleep, quick_sleep * 2)
                        logger.info(
                            f"队友帮助平局完成，随机等待{sleeptime}秒后开始新对局"
                        )
                        await asyncio.sleep(sleeptime)
                        games, win_rate = await game_state(MYID)
                        g["win_rate"] = win_rate
                        await start_my_game(client, games)
                else:
                    logger.warning(f"未知主题{message.topic}")
        except aiomqtt.exceptions.MqttCodeError as ee:
            logger.error("MQTT异常，尝试重新连接: %s", ee, exc_info=True)
            raise
        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}", exc_info=True)
            await asyncio.sleep(10)


async def start_game(client: Client):
    sw_flag1 = False
    sw_flag2 = False
    while True:
        g["auto_time"] = is_within_time_ranges(auto_time)
        g["natural_time"] = is_within_time_ranges(natural_mode_time)
        is_active = g["auto_time"] or g["natural_time"]

        if is_active:
            if g["auto_time"] and not sw_flag1:
                sw_flag1 = True
                logger.info(
                    "当前时间段为挂机时间，启动！！！！！！！！！！！！！！！！！！！！！！！！！！！！"
                )

            if g["natural_time"] and not sw_flag2:
                sw_flag2 = True
                logger.info(
                    "当前时间段为自然开局时间，启动！！！！！！！！！！！！！！！！！！！！！！！！！！！！"
                )

            try:
                games, win_rate = await game_state(MYID)
                g["win_rate"] = win_rate
                if MYID not in games:
                    await start_my_game(client, games)
                delta = random.randint(-sleep // 10, sleep // 10)
                await asyncio.sleep(sleep + delta)

            except aiomqtt.exceptions.MqttCodeError as ee:
                logger.error("MQTT异常，尝试重新连接: %s", ee, exc_info=True)
                raise

            except Exception as e:
                logger.error("任务执行失败：%s", e, exc_info=True)
                await asyncio.sleep(5)
        else:
            if sw_flag1 or sw_flag2:
                sw_flag1 = False
                sw_flag2 = False
                logger.info(
                    "当前时间段为休息时间，关闭。。。。。。。。。。。。。。。。。。。。。。。。。。。。"
                )
            await asyncio.sleep(10)


async def _play_game():
    while True:
        async with lock:
            game_list = await get_gamelist(friends, play_point)
            if not game_list:
                return
            data = random.choice(game_list)
            logger.info(f"对局数据:{data}")
            point = 21 if data["amount"] == "100.0" else 17
            if not await do_game(data, point, "对局"):
                return
        await asyncio.sleep(random.randint(1, 5))


async def play_game():
    while auto_play:
        g["play_time"] = is_within_time_ranges(play_time)
        if g["play_time"]:
            try:
                await _play_game()
                delta = random.randint(-play_sleep // 10, play_sleep // 10)
                await asyncio.sleep(play_sleep + delta)
            except Exception as e:
                logger.error(f"自动对局发生错误: {e}", exc_info=True)
        else:
            await asyncio.sleep(10)


def is_within_time_ranges(time_ranges):
    now = datetime.now().time()
    for start_str, end_str in time_ranges:
        start = time_class.fromisoformat(start_str)
        end = time_class.fromisoformat(end_str)
        if start <= now <= end:
            return True
    return False


async def main():
    if MYID not in friends:
        logger.error("非授权用户，请联系YY")
        return
    client = Client(
        HOST,
        username=MQTT_USER,
        password=MQTT_PASSWORD,
        identifier=f"{MYID}_{hash(time_module.time())}",
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


if __name__ == "__main__":
    asyncio.run(main())
