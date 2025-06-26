from libs.game import boom_game, do_game, game_state
from libs.mqtt import Client, HOST
from libs.log import logger
from libs.toml import read
import json, asyncio

HELP_TOPIC = "blackjack/help"
GAME_TOPIC = "blackjack/games"
config = read("config/config.toml")
MYID = config["GAME"]["MYID"]

lock = asyncio.Lock()

async def help():
    boom_data = {
        "game": "hit",
        "start": "yes",
        "userid": 0,
        "amount": 0,
    }
    async with Client(HOST) as client:
        try:
            await client.subscribe(HELP_TOPIC)
            async for message in client.messages:
                async with lock:
                    data = json.loads(message.payload)
                    userid = data["userid"]
                    if not (userid == MYID):
                        if data.get("point", 0) > 21:
                            boom_data["userid"] = userid
                            boom_data["amount"] = data["amount"]
                            await boom_game(boom_data, MYID)
                    else:
                        logger.info("自己的消息，不平局")
        except Exception as e:
            logger.error(e)


async def start_my_game():
    amount = config["GAME"]["bonus"]
    remain_point = config["GAME"]["remain_point"]
    async with Client(HOST) as client:
        await client.subscribe(GAME_TOPIC)
        async for message in client.messages:
            try:
                async with lock:
                    data = json.loads(message.payload)
                    if MYID not in data:
                        point = await do_game(amount, remain_point)
                        if point and point > 21:
                            await client.publish(
                                HELP_TOPIC,
                                payload=json.dumps(
                                    {"userid": MYID, "amount": amount, "point": point}
                                ),
                            )
            except Exception as e:
                logger.error(e)


async def fetch_games():
    sleep = config["GAME"].get("sleep", 60)
    async with Client(HOST) as client:
        while True:
            try:
                games = await game_state(MYID)
                await client.publish(
                    GAME_TOPIC,
                    payload=json.dumps(games),
                )
            except Exception as e:
                logger.error(e)
            finally:
                await asyncio.sleep(sleep)


async def main():
    await asyncio.gather(help(), start_my_game(), fetch_games())


if __name__ == "__main__":
    asyncio.run(main())
