"""
$description Chinese live-streaming platform
$url weibo.com
$type live
$metadata id
$metadata author
$metadata title
"""
import json
import logging
import re
from typing import Dict

from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream import HLSStream

log = logging.getLogger(__name__)


@pluginmatcher(
    re.compile(
        r"https?://(?:zh\.)?stripchat\.com/(?P<channel>[^/?]+)",
    ),
)
class Weibo(Plugin):
    QUALITY_WEIGHTS: Dict[str, int] = {}

    @classmethod
    def stream_weight(cls, key):
        weight = cls.QUALITY_WEIGHTS.get(key)
        if weight:
            return weight, key

        return super().stream_weight(key)

    def get_weibo_stream_data(self, url: str) -> dict:
        headers = {
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Cookie': 'XSRF-TOKEN=qAP-pIY5V4tO6blNOhA4IIOD; SUB=_2AkMRNMCwf8NxqwFRmfwWymPrbI9-zgzEieKnaDFrJRMxHRl-yT9kqmkhtRB6OrTuX5z9N_7qk9C3xxEmNR-8WLcyo2PM; SUBP=0033WrSXqPxfM72-Ws9jqgMF55529P9D9WWemwcqkukCduUO11o9sBqA; WBPSESS=Wk6CxkYDejV3DDBcnx2LOXN9V1LjdSTNQPMbBDWe4lO2HbPmXG_coMffJ30T-Avn_ccQWtEYFcq9fab1p5RR6PEI6w661JcW7-56BszujMlaiAhLX-9vT4Zjboy1yf2l',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
        }

        self.session.http.headers.update(headers)

        room_id = ''
        if 'show/' in url:
            room_id = url.split('?')[0].split('show/')[1]
        else:
            uid = url.split('?')[0].rsplit('/u/', maxsplit=1)[1]
            web_api = f'https://weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0'
            json_str = self.session.http.get(web_api)
            json_data = json.loads(json_str)
            for i in json_data['data']['list']:
                if 'page_info' in i and i['page_info']['object_type'] == 'live':
                    room_id = i['page_info']['object_id']
                    break

        result = {"anchor_name": '', "is_live": False}
        if room_id:
            app_api = f'https://weibo.com/l/pc/anchor/live?live_id={room_id}'
            json_str = self.session.http.get(url=app_api)
            json_data = json.loads(json_str)
            anchor_name = json_data['data']['user_info']['name']
            result["anchor_name"] = anchor_name
            live_status = json_data['data']['item']['status']
            if live_status == 1:
                result["is_live"] = True
                live_title = json_data['data']['item']['desc']
                play_url_list = json_data['data']['item']['stream_info']['pull']
                m3u8_url = play_url_list['live_origin_hls_url']
                flv_url = play_url_list['live_origin_flv_url']
                result['title'] = live_title
                result['play_url_list'] = [
                    {"m3u8_url": m3u8_url, "flv_url": flv_url},
                    {"m3u8_url": m3u8_url.split('_')[0] + '.m3u8', "flv_url": flv_url.split('_')[0] + '.flv'}
                ]
        return result

    def is_online(self):
        try:
            channel = self.match.group("channel")
            resp = self.session.http.get(f'https://stripchat.com/api/front/v2/models/username/{channel}/cam').json()
            if 'cam' in resp and 'isCamAvailable' in resp['cam'] and resp['cam']['isCamAvailable']:
                hls_url = f'https://edge-hls.doppiocdn.net/hls/{resp["cam"]["streamName"]}/master/{resp["cam"]["streamName"]}.m3u8'
                self.title = ''
                self.author = channel
                self.id = resp["cam"]["streamName"]
                return True, hls_url
            else:
                return False, None
        except:
            return False, None

    def _get_streams(self):
        is_online, hls_url = self.is_online()
        if not is_online:
            log.error("This stream is currently offline")
            return

        playlist = HLSStream.parse_variant_playlist(self.session, hls_url)

        for k in playlist:
            yield k, playlist[k]

        log.debug(f"QUALITY_WEIGHTS: {self.QUALITY_WEIGHTS!r}")


__plugin__ = Weibo
