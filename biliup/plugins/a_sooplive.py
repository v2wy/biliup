import asyncio
import json
import subprocess

import streamlink
from streamlink import NoPluginError

from biliup.config import config
from ..engine.decorators import Plugin
from ..engine.download import DownloadBase
from ..plugins import logger


@Plugin.download(regexp=r"https?://(.*?)\.sooplive\.co\.kr/(?P<username>\w+)(?:/\d+)?")
class SoopliveKr(DownloadBase):
    session: streamlink.session.Streamlink
    username: str
    password: str

    def __init__(self, fname, url, suffix='mkv'):
        self.username = config.get('user', {}).get('afreecatv_username', '')
        self.password = config.get('user', {}).get('afreecatv_password', '')
        DownloadBase.__init__(self, fname, url, suffix=suffix)
        self.session = streamlink.session.Streamlink({
            'stream-segment-timeout': 60,
            'hls-segment-queue-threshold': 10,
            'stream-segment-threads': 3,
            'soop-username': self.username,
            'soop-password': self.password,
        })

        self.is_download = False
        self.downloader = 'streamlink'

    async def acheck_stream(self, is_check=False):
        loop = asyncio.get_running_loop()
        try:
            plugin_name, plugin_type, url = await loop.run_in_executor(
                None,  # 使用默认线程池
                lambda: self.session.resolve_url(self.url)
            )
            logger.debug(f'{url}匹配到插件 ' + plugin_name)
        except NoPluginError:
            logger.error('url没有匹配到插件 ' + self.url)
            return False

        streams = await loop.run_in_executor(
            None,  # 使用默认线程池
            lambda: self.session.streams(self.url)
        )
        if streams is None:
            return False

        res = streams.get('best')

        if res is None:
            return False

        result = await loop.run_in_executor(
            None,  # 使用默认线程池
            lambda: subprocess.run(
                ['streamlink', '--soop-username', self.username, '--soop-password', self.password, '-j', url],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
        )

        info = json.loads(result)

        logger.info(info)

        self.raw_stream_url = res.url
        if type(info) is dict and info and 'streams' in info and 'best' in info['streams']:
            self.raw_stream_url = info['streams']['best']['url']
            if '1080p60' in info['streams']:
                self.raw_stream_url = info['streams']['1080p60']['url']
            self.fake_headers = info['streams']['best']['headers']
            if '1080p60' in info['streams']:
                self.fake_headers = info['streams']['1080p60']['headers']
        self.room_title = ''
        if type(info) is dict and info and 'metadata' in info and 'title' in info['metadata']:
            self.room_title = info['metadata']['title']

        logger.info(self.room_title, self.fake_headers, self.room_title)

        return True
