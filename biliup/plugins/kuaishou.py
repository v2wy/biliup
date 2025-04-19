import json
import os
import random
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

        room_info = {}
        try_time = 3
        while try_time > 0:
            try:
                session = requests_html.HTMLSession()
                proxy_config = get_random_proxy()
                logger.info(f"代理配置：{proxy_config}")

                err_keys = ["错误代码22", "主播尚未开播", "请求过快，请稍后重试"]
                logger.info("请求：" + f"https://live.kuaishou.com/u/{room_id}")
                html = (session.get(f"https://live.kuaishou.com/u/{room_id}", timeout=10, proxies=proxy_config)).text
                for key in err_keys:
                    if key in html:
                        logger.info(f"{plugin_msg}: {key}")
                        return False

                room_info = (session.get(
                    f"https://live.kuaishou.com/live_api/liveroom/livedetail?principalId={room_id}",
                    timeout=10, proxies=proxy_config)).json()['data']
                break
            except Exception as e:
                logger.error(f"Kuaishou - {self.url}: {e}")
                try_time -= 1
                time.sleep(5)

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

        logger.info(f"直播间信息: {json.dumps(room_info, ensure_ascii=False)}")

        # if is_check:
        #     return True
        self.room_title = room_info['author']['name']
        if 'caption' in room_info['liveStream']:
            self.room_title = room_info['liveStream']['caption']

        if 'hlsPlayUrl' in room_info['liveStream'] and room_info['liveStream']['hlsPlayUrl'] != '':
            raw_stream_url = room_info['liveStream']['hlsPlayUrl']
        elif 'hevc' in room_info['liveStream']['playUrls']:
            raw_stream_url = room_info['liveStream']['playUrls']['hevc']['adaptationSet']['representation'][-1]['url']
        elif 'h264' in room_info['liveStream']['playUrls']:
            raw_stream_url = room_info['liveStream']['playUrls']['h264']['adaptationSet']['representation'][-1]['url']
        else:
            raw_stream_url = room_info['liveStream']['playUrls'][0]['adaptationSet']['representation'][-1]['url']
        logger.info(raw_stream_url)
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


def get_random_proxy():
    """
    从 proxies.txt 中随机读取一个代理配置，返回格式为字典：
    {
        "http": "socks5://user:pass@ip:port",
        "https": "socks5://user:pass@ip:port"
    }
    如果文件不存在或内容无效，返回 None。
    """
    # 检查文件是否存在
    if not os.path.exists("proxies.txt"):
        return None

    # 读取文件内容并过滤空行
    with open("proxies.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    # 无有效代理时返回 None
    if not lines:
        return None

    # 随机选择一个代理
    proxy = random.choice(lines)

    # 构造代理字典（同时支持 HTTP/HTTPS）
    return {
        "http": proxy,
        "https": proxy
    }
