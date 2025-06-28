import time as time_module
from datetime import time as time_class
from datetime import datetime
import traceback
from libs.game import boom_game, do_game, game_state
from libs.mqtt import Client
from libs.log import logger
from libs.toml import read
import json, asyncio, random
import aiomqtt
from aiomqtt import MqttError, Message



HELP_TOPIC = "blackjack/help"
GAME_TOPIC = "blackjack/games"
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


async def help(_: Client, message: Message):
    async with lock:
        data = json.loads(message.payload)
        userid = data["userid"]
        if not (userid == MYID):
            if data.get("point", 0) > 21:
                boom_data = {
                    "game": "hit",
                    "start": "yes",
                    "userid": userid,
                    "amount": data["amount"],
                }
                await boom_game(boom_data, MYID)
        else:
            logger.debug("自己的消息，不平局")


async def start_my_game(client: Client, message: Message):
    async with lock:
        data = json.loads(message.payload)
        if MYID not in data:
            # 读取下注点数，如果不是100, 1000, 10000, 100000，强制改成100
            amount = config["GAME"].get("bonus", 100)
            if amount not in [100, 1000, 10000, 100000]:
                amount = 100
            # 读取保留点数，默认值18
            remain_point = config["GAME"].get("remain_point", 18)
            # 读取自助模式，默认值false
            gift_model = config["GAME"].get("gift_model", False)
            gift_remain_point = config["GAME"].get("gift_remain_point", 20)
            gift_bonus = config["GAME"].get("gift_bonus", 100)
            if gift_bonus not in [100, 1000, 10000, 100000]:
                gift_bonus = 100

            natural_remain_point = config["GAME"].get("natural_remain_point", 16)            
            natural_bonus = config["GAME"].get("natural_bonus", 100)
            if natural_bonus not in [100, 1000, 10000, 100000]:
                natural_bonus = 100

            # 计算本局是否自助
            boom_rate = config["GAME"].get("boom_rate", 0)
            boom = random.random() < boom_rate
            win_rate = config["GAME"].get("win_rate", 0.58)
            if g["win_rate"] > win_rate:
                logger.info(f"当前胜率{g["win_rate"]}超过{win_rate},自动开启自助")
                gift_model = True
            if gift_model:
                remain_point = gift_remain_point
                amount = gift_bonus
            elif g["natural_time"]:
                remain_point = natural_remain_point
                amount = natural_bonus            
            point = await do_game(amount, remain_point)
            if point and point > 21:
                if not (g["natural_time"] or gift_model or boom):
                    await client.publish(
                        HELP_TOPIC,
                        payload=json.dumps(
                            {
                                "userid": MYID,
                                "amount": amount,
                                "point": point,
                            }
                        ),
                    )

async def listen(client: Client):
    try:
        async for message in client.messages:
            if message.topic.matches(HELP_TOPIC):
                await help(client, message)
            elif message.topic.matches(GAME_TOPIC) and MYID > 0:
                if g["natural_time"] or g["auto_time"]:
                    await start_my_game(client, message)
            else:
                logger.warning(f"未知主题{message.topic}")
    except Exception as e:
        print(f"处理消息时发生错误: {e}")


async def fetch_games(client: Client):
    sw_flag1 = False
    sw_flag2 = False
    time_ranges = [
        ('00:01','00:35'),
        ('08:00','11:00'),
        ('12:00','15:00'),
        ('16:00','18:00'),
        ('19:30','21:30'),
        ('22:30','23:50'),        
    ]
    auto_time = config["GAME"].get("auto_time", time_ranges)
    natural_mode_time = config["GAME"].get("natural_mode_time", [])
    sleep = config["GAME"].get("sleep", 60)
    while True:
            
        g["auto_time"] = is_within_time_ranges(auto_time)
        g["natural_time"] = is_within_time_ranges(natural_mode_time)
        is_active = g["auto_time"] or g["natural_time"]
      
        if is_active:           
            if g["auto_time"] and not sw_flag1:
                sw_flag1 = True
                logger.info("当前时间段为挂机时间，启动！！！！！！！！！！！！！！！！！！！！！！！！！！！！")

            if g["natural_time"] and not sw_flag2:
                sw_flag2 = True
                logger.info("当前时间段为自然开局时间，启动！！！！！！！！！！！！！！！！！！！！！！！！！！！！")

            try:
                games, win_rate = await game_state(MYID)
                g["win_rate"] = win_rate

                await client.publish(
                    GAME_TOPIC,
                    payload=json.dumps(games),
                )
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
                logger.info("当前时间段为休息时间，关闭。。。。。。。。。。。。。。。。。。。。。。。。。。。。")
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
                await asyncio.gather(listen(client), fetch_games(client))
        except MqttError:
            logger.error(f"Connection lost; Reconnecting in {interval} seconds ...")
            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(e, exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
