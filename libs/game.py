import asyncio
import aiohttp
import random
from bs4 import BeautifulSoup
from libs.log import logger
from libs.toml import read

config_basic = read("config/config.toml")["BASIC"]
language = config_basic.get("LANGUAGE", "zh-CN,zh")
cookie = config_basic.get("COOKIE", "zh-CN,zh")
sec_ch_ua = config_basic.get(
    "SEC_CH_UA", '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"'
)
sec_fetch_dest = config_basic.get("SEC_FETCH_DEST", "document")
sec_fetch_mode = config_basic.get("SEC_FETCH_MODE", "cors")
user_agent = config_basic.get(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
)
url = "https://springsunday.net/blackjack.php"
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": language,
    "Cookie": cookie,
    # "Origin": "https://springsunday.net",
    "Priority": "u=0, i",
    "Referer": "https://springsunday.net/blackjack.php",
    "Sec-Ch-Ua": sec_ch_ua,
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": sec_fetch_dest,
    "Sec-Fetch-Mode": sec_fetch_mode,
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "upgrade-insecure-requests": "1",
    "User-Agent": user_agent,
}


def extract_form_params(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    """
    Extract parameters from all forms, using submit button text as key.

    Args:
        soup (BeautifulSoup): Parsed HTML content

    Returns:
        Dict[str, Dict[str, str]]: Dictionary with submit button text as key
        and form input name-value pairs as value
    """
    result = {}
    forms = soup.find_all("form")

    for form in forms:
        # Get submit button text
        submit_button = form.find("input", {"type": "submit"})
        submit_text = (
            submit_button.get("value", "").strip()
            if submit_button
            else "No Submit Button"
        )

        # Extract all input parameters
        params = {}
        inputs = form.find_all("input")
        for input_tag in inputs:
            name = input_tag.get("name")
            value = input_tag.get("value")
            if name and value:
                params[name] = value

        # Only add to result if there are parameters
        if params:
            result[submit_text] = params

    return result


async def game(data):
    err = 0
    while err < 3:
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(10)
            ) as session:
                async with session.post(url, headers=headers, data=data) as response:
                    if response.status == 200:
                        soup = BeautifulSoup(await response.text(), "lxml")
                        forms = extract_form_params(soup)
                        element = soup.select_one("#details b")
                        logger.debug(forms)
                        if element:
                            text = element.get_text(strip=True)
                            try:
                                point_str = text.split("=")[-1].strip()
                                if point_str:
                                    if point_str == "21或更多":
                                        logger.info("可能超过21点，按22点计算")
                                        point = 22
                                    else:
                                        point = int(point_str)
                                else:
                                    raise
                            except:
                                logger.error("未能获取到页面点数，返回22")
                                point = 22
                            return point, forms
                        else:
                            element = soup.select_one(
                                "#outer table table td"
                            ) or soup.select_one("form strong")
                            if element:
                                logger.warning(element.text.strip())
                            logger.error("未能获取到页面点数，返回None")
                            return None, forms
                    else:
                        raise (response.status)
        except asyncio.TimeoutError as e:
            logger.error(e, exc_info=True)
        except Exception as e:
            logger.error(e, exc_info=True)
        finally:
            err += 1
    return None, {}


async def do_game(data: dict, remain_point=18, log_type="开局"):
    point, forms = await game(data)
    if "继续旧游戏" in forms:
        await asyncio.sleep(1)
        await do_game(forms["继续旧游戏"], 17, "未知")
        await asyncio.sleep(2)
        return await do_game(data, remain_point, log_type)
    if not point:
        if forms:
            logger.error(f"未知页面{forms}")
        return None
    while point < remain_point:
        logger.info(f"[{log_type}]当前点数{point}，继续抓牌")
        if "再抓一张" in forms:
            await asyncio.sleep(random.randint(1, 5))
            point, forms = await game(forms["再抓一张"])
    logger.info(f"[{log_type}]当前点数{point}，结束")
    if "不再抓了，结束" in forms:
        point, forms = await game(forms["不再抓了，结束"])
    return point


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


def games_list_form_params(
    soup: BeautifulSoup, no_bet_list: list, max_amount: int
) -> dict[str, dict[str, str]]:
    result = []
    forms = soup.find_all("form")

    for form in forms:
        # Extract all input parameters
        params = {}
        inputs = form.find_all("input")
        for input_tag in inputs:
            name = input_tag.get("name")
            value = input_tag.get("value")
            if name and value:
                params[name] = value

        # Only add to result if there are parameters
        if (
            params
            and "userid" in params
            and int(params["userid"]) not in no_bet_list
            and int(params["amount"].split(".")[0]) <= max_amount
        ):
            result.append(params)

    return result


async def get_gamelist(no_bet_list, max_point):
    error = 0
    while error < 3:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        soup = BeautifulSoup(await response.text(), "lxml")
                        game_list = games_list_form_params(soup, no_bet_list, max_point)
                        return game_list
                    else:
                        logger.error(response.status)
                        raise (response.status)
            except Exception as e:
                logger.error(e, exc_info=True)
                error += 1
                logger.error(f"请求错误{error}次")
