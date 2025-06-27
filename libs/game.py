import asyncio
import aiohttp
from bs4 import BeautifulSoup
from libs.log import logger
from libs.toml import read

cookie = read("config/config.toml")["BASIC"]["COOKIE"]
url = "https://springsunday.net/blackjack.php"
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh",
    "Cookie": cookie,
    "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}


async def game(data, url, headers, max_retries=3):
    # 在循环外创建 ClientSession，复用会话
    async with aiohttp.ClientSession() as session:
        for attempt in range(max_retries):
            try:
                # 设置超时：总超时10秒，连接超时5秒，读取超时5秒
                timeout = aiohttp.ClientTimeout(total=10, connect=5, sock_read=5)
                async with session.post(
                    url, headers=headers, data=data, timeout=timeout
                ) as response:
                    if response.status == 200:
                        # 确保响应是 HTML
                        if "text/html" not in response.content_type:
                            logger.error("响应不是 HTML，返回 None")
                            return None, None

                        soup = BeautifulSoup(await response.text(), "lxml")
                        element = soup.select_one("#details b")
                        if element:
                            text = element.get_text(strip=True)
                            try:
                                point_str = text.split("=")[-1].strip()
                                if point_str:
                                    point = int(point_str)
                                    return point, None
                                else:
                                    logger.error("点数字段为空，返回 None")
                                    return None, None
                            except ValueError as e:
                                logger.error(f"点数解析失败: {e}, 返回 None")
                                return None, None
                        else:
                            element = soup.select_one(
                                "#outer table table td"
                            ) or soup.select_one("form strong")
                            if element:
                                message = element.text.strip()
                                logger.warning(f"页面返回提示: {message}")
                                return None, message
                            logger.error("未能获取到页面点数，返回 None")
                            return None, None
                    else:
                        logger.error(f"请求失败，状态码: {response.status}")
                        raise aiohttp.ClientResponseError(
                            status=response.status,
                            message=await response.text(),
                            headers=response.headers,
                            request_info=response.request_info,
                        )

            except asyncio.TimeoutError as e:
                logger.error(f"请求超时: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"第 {attempt + 1} 次重试...")
                    await asyncio.sleep(2)  # 重试前等待2秒
                    continue
                logger.error("达到最大重试次数，返回 None")
                return None, None

            except aiohttp.ClientError as e:
                logger.error(f"网络错误: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"第 {attempt + 1} 次重试...")
                    await asyncio.sleep(2)
                    continue
                logger.error("达到最大重试次数，返回 None")
                return None, None

            except Exception as e:
                logger.error(f"意外错误: {e}", exc_info=True)
                return None, None


async def do_game(amount=100, remain_point=18, my_userid=0):
    start_data = {
        "game": "hit",
        "start": "yes",
        "amount": amount,
    }
    continue_data = {"game": "hit", "continue": "yes", "userid": my_userid}
    hit_data = {"game": "hit", "userid": 0}
    stop_data = {"game": "stop", "userid": 0}
    s, e = await game(start_data)
    while not s:
        if e == "您必须先完成当前的游戏。":
            s, e = await game(continue_data)
            await asyncio.sleep(5)
        else:
            return
    while s < remain_point:
        logger.info(f"当前点数{s}，继续抓牌")
        s_, e = await game(hit_data)
        if s_:
            s = s_
        else:
            if e == "Starship":
                logger.warning("当前点数{s}，对局已结束")
                return s
            else:
                logger.error("当前点数{s}，访问错误，等待重试")
                return None
    if s == 21:
        logger.info(f"当前点数{s}，完美")
    elif s < 21:
        logger.info(f"当前点数{s}，停止抓牌")
        s, e = await game(stop_data)
    else:
        logger.info(f"当前点数{s}，爆了")
    return s


async def boom_game(boom_data, my_userid):
    start_data = boom_data
    hit_data = {"game": "hit", "userid": my_userid}
    stop_data = {"game": "stop", "userid": my_userid}
    s, e = await game(start_data)
    while not s:
        if e == "该对局已结束":
            logger.warning(f"平局：对局被人抢了")
            return None
        elif e == "您必须先完成当前的游戏。":
            logger.warning(f"平局：上局未结束，无法获知对局对象，直接结束")
            await game(stop_data)
            return None
        else:
            logger.warning("平局：链接错误，稍后重试")
            return None
    while s < 21:
        logger.info(f"平局：当前点数{s}，继续抓牌")
        s_, e = await game(hit_data)
        if s_:
            s = s_
        else:
            if e == "Starship":
                logger.warning("平局：对局已结束")
                return None
            logger.error("平局：获取对局数据失败，直接结束")
            await game(stop_data)
            return None
    if s == 21:
        logger.info(f"平局：当前点数{s}，平局失败")
        return s
    else:
        logger.info(f"平局：当前点数{s}，平局成功")
        return s


async def game_state(userid):
    error = 0
    state = []
    while error < 3:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        soup = BeautifulSoup(await response.text(), "lxml")
                        inputs = soup.select(
                            "#game_available tr td:nth-of-type(3) form input[name='userid']"
                        )
                        state = [int(input["value"]) for input in inputs]
                        forms = soup.select("input[value='刷新']")
                        if forms:
                            state.append(userid)
                        win_rate = soup.select_one(
                            "table:nth-of-type(2) tr:nth-of-type(5) td:nth-of-type(2)"
                        )
                        win_rate_num = float(win_rate.text.strip("%")) / 100
                        return state, win_rate_num
                    else:
                        logger.error(response.status)
                        raise (response.status)
            except Exception as e:
                logger.error(e, exc_info=True)
                error += 1
                logger.error(f"请求错误{error}次")


if __name__ == "__main__":
    asyncio.run(do_game())
