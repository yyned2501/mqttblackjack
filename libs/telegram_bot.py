import pyrogram

from libs.toml import config

bot: pyrogram.Client = None
if config.get("BOT.PROXY_SET") == "on":
    proxy = config.get("BOT.PROXY_INFO")
else:
    proxy = None


async def init_bot():
    global bot
    bot = pyrogram.Client(
        "bot",
        api_id=config.get("BOT.API_ID", 26687146),
        api_hash=config.get("BOT.API_HASH", "119ff2d77e1b0e72344c896d4170b613e"),
        bot_token=config.get("BOT.BOT_TOKEN"),
        proxy=proxy,
    )


async def handle_inline_query(client, inline_query):
    await client.answer_inline_query(
        inline_query.id,
        results=[
            {
                "type": "article",
                "id": "1",
                "title": "Blackjack游戏",
                "input_message_content": {
                    "message_text": "点击开始21点游戏"
                },
                "reply_markup": {
                    "inline_keyboard": [[{
                        "text": "开始游戏",
                        "web_app": {"url": "https://yourdomain.com/blackjack_inline"}
                    }]]
                }
            }
        ]
    )


def setup_handlers():
    bot.add_handler(pyrogram.handlers.InlineQueryHandler(handle_inline_query))

