import json
import time

import requests_html

from biliup.config import config
from ..engine.decorators import Plugin
from ..engine.download import DownloadBase
from ..plugins import logger


@Plugin.download(regexp=r'(?:https?://)?(?:(?:live|www|v)\.)?(kuaishou)\.com')
@Plugin.download(regexp=r'(?:https?://)?(?:(?:(?:livev)\.(?:m))\.)?chenzhongtech\.com')
class Kuaishou(DownloadBase):
    def __init__(self, fname, url, suffix='flv'):
        super().__init__(fname, url, suffix)
        self.fake_headers['Cookie'] = config.get('kuaishou_cookie', '')

    async def acheck_stream(self, is_check=False):
        try:
            room_id = get_kwaiId(self.url)
            if not room_id:
                logger.warning(f"Kuaishou - {self.url}: 直播间地址错误")
                return False
        except Exception as e:
            logger.error(f"Kuaishou - {self.url}: {e}")
            return False

        plugin_msg = f"Kuaishou - {room_id}"

        session = requests_html.HTMLSession()
        # 首页低风控生成did
        logger.info("请求：快手直播主页 live.kuaishou.com")
        res = session.get("https://live.kuaishou.com", timeout=5)
        time.sleep(3)
        raw_json = parse_complex_json(res.text.split('__INITIAL_STATE__=')[1])
        obj = json.loads(raw_json)
        id = obj['home']['homeLiveStream'][0]['id']
        url = f'https://live.kuaishou.com/u/{id}'
        logger.info("请求：" + url)
        session.get(url)
        time.sleep(2)

        # # 不暂停似乎容易风控
        # times = 3 + random.random()
        # logger.debug(f"{plugin_msg}: 暂停 {times} 秒")
        # time.sleep(times)

        err_keys = ["错误代码22", "主播尚未开播", "请求过快，请稍后重试"]
        logger.info("请求：" + f"https://live.kuaishou.com/u/{room_id}")
        html = (session.get(f"https://live.kuaishou.com/u/{room_id}", timeout=5)).text
        for key in err_keys:
            if key in html:
                logger.info(f"{plugin_msg}: {key}")
                return False

        room_info = (session.get(
            f"https://live.kuaishou.com/live_api/liveroom/livedetail?principalId={room_id}",
            timeout=5)).json()['data']

        if room_info['result'] == 22:
            logger.error(f"{plugin_msg}: 直播间地址错误")
            return False
        if room_info['result'] == 671:
            logger.debug(f"{plugin_msg}: 直播间未开播或非直播")
            return False
        if room_info['result'] == 2:
            logger.debug(f"{plugin_msg}: 疑似请求过快")
            return False
        if room_info['result'] != 1:
            logger.error(f"{plugin_msg}: {room_info}")
            return False

        if is_check:
            return True

        try:
            self.room_title = room_info['liveStream']['caption']
        except KeyError:
            logger.warning(f"{plugin_msg}: 直播间标题获取失败，使用快手ID代替")
            self.room_title = room_info['author']['name']

        if 'h264' in room_info['liveStream']['playUrls']:
            raw_stream_url = room_info['liveStream']['playUrls']['h264']['adaptationSet']['representation'][-1]['url']
        elif 'hevc' in room_info['liveStream']['playUrls']:
            raw_stream_url = room_info['liveStream']['playUrls']['hevc']['adaptationSet']['representation'][-1]['url']
        else:
            raw_stream_url = room_info['liveStream']['playUrls'][0]['adaptationSet']['representation'][-1]['url']
        self.raw_stream_url = raw_stream_url

        return True


def get_kwaiId(url):
    split_args = ["/profile/", "/fw/live/", "/u/"]
    for key in split_args:
        if key in url:
            kwaiId = url.split(key)[1]
            return kwaiId


def parse_complex_json(script):
    stack = []
    start_index = script.find('{')
    if start_index == -1:
        return None

    stack.append('{')
    end_index = start_index + 1

    while end_index < len(script) and stack:
        char = script[end_index]
        if char == '{':
            stack.append('{')
        elif char == '}':
            stack.pop()
        end_index += 1

    return script[start_index:end_index]
