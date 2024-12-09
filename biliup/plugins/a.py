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


class Ytdlp(DownloadBase):
    def __init__(self, fname, url, suffix='mp4'):
        DownloadBase.__init__(self, fname, url, suffix=suffix)
        self.youtube_cookie = config.get('user', {}).get('youtube_cookie')

        self.is_download = True
        self.downloader = 'ffmpeg'

    async def acheck_stream(self, is_check=False):
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
        if is_check:
            return True
        self.raw_stream_url = info['url']
        self.room_title = info['title']
        self.fake_headers = info['http_headers'].data
        return True


class StreamLink(DownloadBase):
    session: streamlink.session.Streamlink

    def __init__(self, fname, url, suffix='mp4'):
        DownloadBase.__init__(self, fname, url, suffix=suffix)
        self.session = streamlink.session.Streamlink({
            'stream-segment-timeout': 60,
            'hls-segment-queue-threshold': 10,
            'stream-segment-threads': 10
        })
        streamlink_plugins_dir = 'streamlink_plugins'
        if os.path.exists(streamlink_plugins_dir):
            self.session.plugins.load_path(streamlink_plugins_dir)

        self.is_download = True
        self.downloader = 'ffmpeg'

    async def acheck_stream(self, is_check=False):
        try:
            plugin_name, plugin_type, url = self.session.resolve_url(self.url)
            logger.debug(f'{url}匹配到插件 ' + plugin_name)
        except NoPluginError:
            logger.error('url没有匹配到插件 ' + self.url)
            return False
        streams = self.session.streams(self.url)
        if streams is None:
            return False

        res = streams.get('best')

        if res is None:
            return False

        if is_check:
            return True

        result = subprocess.run(
            ['streamlink', '--plugin-dir', 'streamlink_plugins', '-j', '--twitch-proxy-playlist',
             'https://lb-eu.cdn-perfprod.com', url],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout

        info = json.loads(result)

        self.raw_stream_url = res.url
        if type(info) is dict and info and 'streams' in info and 'best' in info['streams']:
            self.raw_stream_url = info['streams']['best']['url']
            self.fake_headers = info['streams']['best']['headers']
        self.room_title = ''
        if type(info) is dict and info and 'metadata' in info and 'title' in info['metadata']:
            self.room_title = info['metadata']['title']

        return True


@Plugin.download(regexp=r'(?:https?://)?(chaturbate\.com)/(?P<id>.*?)/')
class Chaturbate(Ytdlp):
    pass


# https://17.live/en-US/profile/r/15519172
# https://17.live/en-US/live/15519172
@Plugin.download(regexp=r'(?:https?://)?(17\.live/[a-zA-z-]+/(profile/r|live))/(?P<id>.*?)')
class X17Live(Ytdlp):
    def __init__(self, fname, url, suffix='mp4'):
        super().__init__(fname, url, suffix)
        self.is_download = False
        self.downloader = 'stream-gears'


# https://chzzk.naver.com/live/1b0561f3051c10a24b9d8ec9a6cb3374
@Plugin.download(regexp=r'(?:https?://)?(chzzk\.naver\.com)/live/(?P<id>.*?)')
class Chzzk(Ytdlp):
    pass


@Plugin.download(regexp=r'(?:https?://)?(zh\.)?(stripchat\.com)/(?P<id>.*?)')
class Stripchat(StreamLink):
    pass


@Plugin.download(regexp=r'(?:https?://)?(?:(?:www|go|m)\.)?twitch\.tv/(?P<id>[0-9_a-zA-Z]+)')
class Twitch(StreamLink):
    pass


# https://www.tiktok.com/@ignobitaofficial/live
@Plugin.download(regexp=r'(?:https?://)?(?:(?:www|go|m)\.)?tiktok\.com/@(?P<id>[0-9_a-zA-Z]+)/live')
class Tiktok(StreamLink):
    def __init__(self, fname, url, suffix='mp4'):
        super().__init__(fname, url, suffix)
        self.is_download = False
        self.downloader = 'stream-gears'


# https://www.pandalive.co.kr/live/play/queen486
@Plugin.download(regexp=r'(?:https?://)?(?:(?:www)\.)?pandalive\.co\.kr/live/play/(?P<id>[0-9_a-zA-Z]+)')
class Pandalive(StreamLink):
    pass
