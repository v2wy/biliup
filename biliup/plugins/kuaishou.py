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

        room_info = {}
        try_time = 3
        while try_time > 0:
            try:
                session = requests_html.HTMLSession()
                proxy_config = self.get_random_proxy()
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

        kuaishou_prefer = self.conf('kuaishou_prefer')
        if kuaishou_prefer:
            if kuaishou_prefer == 'hls' and 'hlsPlayUrl' in room_info['liveStream'] and room_info['liveStream'][
                'hlsPlayUrl'] != '':
                raw_stream_url = room_info['liveStream']['hlsPlayUrl']
                logger.info(f"根据kuaishou_prefer配置{kuaishou_prefer}修改为新的raw_stream_url")
            elif kuaishou_prefer == 'hevc' and 'hevc' in room_info['liveStream']['playUrls']:
                kuaishou_quality_type = self.conf('kuaishou_quality_type')
                for representation in room_info['liveStream']['playUrls']['hevc']['adaptationSet']['representation']:
                    if representation['qualityType'] == kuaishou_quality_type:
                        raw_stream_url = representation['url']
                        # 其他下载器可能不支持hevc
                        self.downloader = 'ffmpeg'
                        logger.info(f"根据kuaishou_prefer配置{kuaishou_prefer}修改为新的raw_stream_url")
            elif kuaishou_prefer == 'h264' and 'h264' in room_info['liveStream']['playUrls']:
                raw_stream_url = room_info['liveStream']['playUrls']['h264']['adaptationSet']['representation'][-1][
                    'url']
                logger.info(f"根据kuaishou_prefer配置{kuaishou_prefer}修改为新的raw_stream_url")

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
