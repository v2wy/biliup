import copy
import os
import shutil
from typing import Optional

import yt_dlp

from yt_dlp import DownloadError
from yt_dlp.utils import DateRange
from biliup.config import config
from ..engine.decorators import Plugin
from . import logger
from ..engine.download import DownloadBase
import requests
from urllib.parse import urlparse
from streamlink.plugin.api import validate
import re

# VALID_URL_BASE = r'https?://(?:(?:www|m)\.)?youtube\.orz\.com/(?P<id>.*?)\??(.*?)'
VALID_URL_BASE = r'(?:https?://)?(?:(?:www|m)\.)?youtube\.com/@(?P<id>.+)(\/.*)?'
session = requests.session()
browseIdMap = {}
fake_headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'accept-encoding': 'gzip, deflate',
    'accept-language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
}


@Plugin.download(regexp=VALID_URL_BASE)
class Youtube(DownloadBase):
    def __init__(self, fname, url, suffix='flv'):
        super().__init__(fname, url, suffix)
        self.ytb_danmaku = config.get('ytb_danmaku', False)
        self.ytb_danmaku = False
        self.youtube_cookie = config.get('user', {}).get('youtube_cookie')
        self.youtube_prefer_vcodec = config.get('youtube_prefer_vcodec')
        self.youtube_prefer_acodec = config.get('youtube_prefer_acodec')
        self.youtube_max_resolution = config.get('youtube_max_resolution')
        self.youtube_max_videosize = config.get('youtube_max_videosize')
        self.youtube_before_date = config.get('youtube_before_date')
        self.youtube_after_date = config.get('youtube_after_date')
        self.youtube_enable_download_live = config.get('youtube_enable_download_live', True)
        self.youtube_enable_download_playback = config.get('youtube_enable_download_playback', True)
        # 需要下载的 url
        self.download_url = None

    async def acheck_stream(self, is_check=False):
        logger.info("is_check: " + str(is_check))
        if is_check:
            return True
        channel = re.match(VALID_URL_BASE, self.url).group('id')
        isLive, streamings = self.get_channel_live_info(channel)
        if not isLive:
            return False
        vod_id = streamings[0]['video_id']
        with yt_dlp.YoutubeDL({
            'download_archive': 'archive.txt',
            'cookiefile': self.youtube_cookie,
            'ignoreerrors': True,
            'extractor_retries': 0,
        }) as ydl:
            video_url = f"https://www.youtube.com/watch?v={vod_id}"
            info = ydl.extract_info(video_url, download=False)
            # print(info)
        self.raw_stream_url = info['url']
        self.room_title = streamings[0]['title1']
        return True

    def get_channel_infos(self, channel):
        channel_id = self.get_channel_id_by_code(channel)

        response = session.request(
            method='POST',
            url='https://www.youtube.com/youtubei/v1/browse',
            params={
                'key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
                'prettyPrint': False
            },
            json={
                'context': {
                    'client': {
                        'hl': 'zh-CN',
                        'clientName': 'MWEB',
                        'clientVersion': '2.20230101.00.00',
                        'timeZone': 'Asia/Shanghai'
                    }
                },
                'browseId': channel_id,
                'params': 'EgdzdHJlYW1z8gYECgJ6AA%3D%3D'
            },
            timeout=5
        ).json()

        return response

    def _schema_consent(self, data):
        schema_consent = validate.Schema(
            validate.parse_html(),
            validate.any(
                validate.xml_find(".//form[@action='https://consent.youtube.com/s']"),
                validate.all(
                    validate.xml_xpath(".//form[@action='https://consent.youtube.com/save']"),
                    validate.filter(
                        lambda elem: elem.xpath(".//input[@type='hidden'][@name='set_ytc'][@value='true']")),
                    validate.get(0),
                ),
            ),
            validate.union((
                validate.get("action"),
                validate.xml_xpath(".//input[@type='hidden']"),
            )),
        )
        return schema_consent.validate(data)

    def get_channel_id_by_code(self, channel):
        if channel not in browseIdMap:
            res = session.get(f"https://www.youtube.com/@{channel}", headers=fake_headers, timeout=5)
            if urlparse(res.url).netloc == "consent.youtube.com":
                target, elems = self._schema_consent(res.text)
                c_data = {
                    elem.attrib.get("name"): elem.attrib.get("value")
                    for elem in elems
                }
                logger.debug(f"consent target: {target}")
                logger.debug(f"consent data: {', '.join(c_data.keys())}")
                res = session.post(target, data=c_data)
            pattern = r'"browseId":"(.*?)"'
            match = re.search(pattern, res.text)
            if match:
                # self.browse_id = match.group(1)
                browseIdMap[channel] = match.group(1)
            else:
                logger.info(f'{channel} 未匹配到 browseId')
                return False, ''
        return browseIdMap[channel]

    def get_channel_live_info(self, channel):
        response = self.get_channel_infos(channel)
        streaming = []
        if not self.get_value_from_json(response,
                                        'contents.singleColumnBrowseResultsRenderer.tabs[3].tabRenderer.content'):
            return False, []
        if not self.get_value_from_json(response,
                                        'contents.singleColumnBrowseResultsRenderer.tabs[3].tabRenderer.content').get(
            "richGridRenderer"):
            return False, []
        contents = self.get_value_from_json(response,
                                            'contents.singleColumnBrowseResultsRenderer.tabs[3].tabRenderer.content.richGridRenderer.contents')
        if not contents:
            return False, []
        for content in contents:
            if not self.get_value_from_json(content, 'richItemRenderer'):
                break
            status = self.get_value_from_json(content,
                                              'richItemRenderer.content.videoWithContextRenderer.thumbnailOverlays[0].thumbnailOverlayTimeStatusRenderer.style')
            if status != 'LIVE':
                break
            streaming.append({
                'video_id': self.get_value_from_json(content,
                                                     'richItemRenderer.content.videoWithContextRenderer.videoId'),
                'title1': self.get_value_from_json(content,
                                                   'richItemRenderer.content.videoWithContextRenderer.headline.runs[0].text'),
                'status': status,
            })
        if streaming:
            return True, streaming
        return False, []

    def get_value_from_json(self, json_data, json_path):
        keys = json_path.split('.')
        result = json_data
        for key in keys:
            if result is None:
                return None
            if '[' in key and ']' in key:
                key, index = key.split('[')
                index = int(index.strip(']'))
                if result.get(key) is None:
                    return None
                if len(result.get(key)) < index + 1:
                    return None
                result = result[key][index]
            else:
                result = result[key]

        return result