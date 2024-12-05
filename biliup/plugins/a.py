import json
import os.path
import subprocess

import yt_dlp
from streamlink import NoPluginError

from biliup.config import config
from . import logger
from ..engine.decorators import Plugin
from ..engine.download import DownloadBase
import streamlink
from .afreecaTV import AfreecaTV


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
    session: streamlink.session.Streamlink

    def __init__(self, fname, url, suffix='flv'):
        DownloadBase.__init__(self, fname, url, suffix=suffix)
        self.session = streamlink.session.Streamlink({
            'stream-segment-timeout': 60,
            'hls-segment-queue-threshold': 10,
            'stream-segment-threads': 10
        })
        streamlink_plugins_dir = 'streamlink_plugins'
        if os.path.exists(streamlink_plugins_dir):
            self.session.plugins.load_path(streamlink_plugins_dir)

    async def acheck_stream(self, is_check=False):
        if is_check:
            return True
        try:
            plugin_name, plugin_type, url = self.session.resolve_url(self.url)
            logger.info(f'{url}匹配到插件 ' + plugin_name)
        except NoPluginError:
            logger.error('url没有匹配到插件 ' + self.url)
            return False
        streams = self.session.streams(self.url)
        if streams is None:
            return False

        res = streams.get('best')

        if res is None:
            return False

        result = subprocess.run(
            ['streamlink', '--plugin-dir', 'streamlink_plugins', '-j', '--twitch-proxy-playlist',
             'https://lb-eu.cdn-perfprod.com', url],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout

        info = json.loads(result)

        self.raw_stream_url = res.url
        self.room_title = ''
        if type(info) is dict and info and 'metadata' in info and 'title' in info['metadata']:
            self.room_title = info['metadata']['title']

        return True


@Plugin.download(regexp=r'(?:https?://)?(chaturbate\.com)/(?P<id>.*?)/')
class Chaturbate(Ytdlp):
    pass


@Plugin.download(regexp=r'(?:https?://)?(zh\.)?(stripchat\.com)/(?P<id>.*?)')
class Stripchat(StreamLink):
    def __init__(self, fname, url, suffix='flv'):
        StreamLink.__init__(self, fname, url, suffix=suffix)
        self.downloader = 'ffmpeg'


@Plugin.download(regexp=r'(?:https?://)?(?:(?:www|go|m)\.)?twitch\.tv/(?P<id>[0-9_a-zA-Z]+)')
class Twitch(StreamLink):
    pass


@Plugin.download(regexp=r"https?://(.*?)\.sooplive\.co\.kr/(?P<username>\w+)(?:/\d+)?")
class Sooplive(AfreecaTV):
    def __init__(self, fname, url, suffix='flv'):
        self.url = str(url).replace('sooplive.co.kr', 'afreecatv.com')
        super().__init__(fname, self.url, suffix)
