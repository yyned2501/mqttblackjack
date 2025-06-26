import asyncio
import json
from aiomqtt import Client

import sys, os

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy

    set_event_loop_policy(WindowsSelectorEventLoopPolicy())

HOST = "1.94.183.109"
TOPIC = "blackjack/game"


async def publish(x):
    async with Client(HOST) as client:
        await client.publish(TOPIC, payload=json.dumps({"msg": x}))


async def subscribe(topic):
    async with Client(HOST) as client:
        await client.subscribe(topic)
        async for message in client.messages:
            print(json.loads(message.payload))


async def main():
    await asyncio.gather(
        subscribe(TOPIC),
    )


if __name__ == "__main__":
    asyncio.run(main())
