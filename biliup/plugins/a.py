import io
import json
import os.path
import random
import re
import socket
import subprocess
import time
from typing import AsyncGenerator, List
from urllib.parse import urlencode

import yt_dlp
from streamlink import NoPluginError

from biliup.common.util import client
from biliup.config import config
from biliup.Danmaku import DanmakuClient
from . import logger
from ..engine.decorators import Plugin
from ..engine.download import DownloadBase, BatchCheck
import streamlink


class Ytdlp(DownloadBase):
    def __init__(self, fname, url, suffix='flv'):
        DownloadBase.__init__(self, fname, url, suffix=suffix)
        self.youtube_cookie = config.get('user', {}).get('youtube_cookie')

    async def acheck_stream(self, is_check=False):
        if is_check:
            return True
        with yt_dlp.YoutubeDL({
            'download_archive': 'archive.txt',
            'cookiefile': self.youtube_cookie,
            'ignoreerrors': True,
            'extractor_retries': 0,
        }) as ydl:
            info = ydl.extract_info(self.url, download=False)
        if info is None:
            return False
        if type(info) is not dict:
            logger.error(f'[{self.url}] info不为dict ' + json.dumps(info, ensure_ascii=False))
            return False
        if 'is_live' not in info:
            logger.info(f'[{self.url}] is_live不存在 ' + json.dumps(info, ensure_ascii=False))
            return False
        if not info['is_live']:
            logger.info(f'[{self.url}] is_live不为true ' + json.dumps(info, ensure_ascii=False))
            return False
        if info['live_status'] != 'is_live':
            logger.info(f'[{self.url}] live_status不为is_live ' + json.dumps(info, ensure_ascii=False))
            return False
        self.raw_stream_url = info['url']
        self.room_title = info['title']
        return True


class StreamLink(DownloadBase):
    def __init__(self, fname, url, suffix='flv'):
        DownloadBase.__init__(self, fname, url, suffix=suffix)

    async def acheck_stream(self, is_check=False):
        if is_check:
            return True
        session = streamlink.session.Streamlink({
            'stream-segment-timeout': 60,
            'hls-segment-queue-threshold': 10,
            'stream-segment-threads': 10
        })
        streamlink_plugins_dir = 'streamlink_plugins'
        if os.path.exists(streamlink_plugins_dir):
            session.plugins.load_path(streamlink_plugins_dir)
        try:
            plugin_name, plugin_type, url = session.resolve_url(self.url)
        except NoPluginError:
            logger.error('url没有匹配到插件 ' + self.url)
            return False
        streams = session.streams(self.url)
        if streams is None:
            return False

        res = streams.get('best')

        if res is None:
            return False

        self.raw_stream_url = res.url
        self.room_title = ''

        return True


@Plugin.download(regexp=r'(?:https?://)?(chaturbate\.com)/(?P<id>.*?)/')
class Chaturbate(Ytdlp):
    pass


@Plugin.download(regexp=r'(?:https?://)?(zh\.)?(stripchat\.com)/(?P<id>.*?)')
class Stripchat(StreamLink):
    def __init__(self, fname, url, suffix='flv'):
        StreamLink.__init__(self, fname, url, suffix=suffix)
        self.downloader = 'ffmpeg'
    # def download(self):
    #     pass
