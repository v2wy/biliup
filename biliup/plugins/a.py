import asyncio
import json
import os.path
import subprocess

import streamget
import streamlink
import yt_dlp
from streamlink import NoPluginError

from biliup.config import config
from . import logger
from ..Danmaku import DanmakuClient
from ..engine.decorators import Plugin
from ..engine.download import DownloadBase


class Ytdlp(DownloadBase):
    def __init__(self, fname, url, suffix='mkv'):
        DownloadBase.__init__(self, fname, url, suffix=suffix)
        self.youtube_cookie = config.get('user', {}).get('youtube_cookie')

        self.is_download = False
        self.downloader = 'ffmpeg'

    async def acheck_stream(self, is_check=False):
        options = {
            'cookiefile': self.youtube_cookie,
            'ignoreerrors': True,
            'extractor_retries': 0,
        }
        proxies_map = self.conf('proxies_map')
        if proxies_map and proxies_map.get(self.fname):
            logger.info(f"{self.fname} 使用代理 {proxies_map[self.fname]}")
            options.update({
                'proxy': proxies_map[self.fname],
            })
        with yt_dlp.YoutubeDL(options) as ydl:
            loop = asyncio.get_running_loop()
            # 在后台线程中运行 ydl.extract_info
            info = await loop.run_in_executor(
                None,  # 使用默认线程池
                lambda: ydl.extract_info(self.url, download=False)
            )
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
        # logger.debug(info)
        self.fake_headers = dict(info['http_headers'])
        return True


class StreamLink(DownloadBase):
    session: streamlink.session.Streamlink

    def __init__(self, fname, url, suffix='mkv'):
        DownloadBase.__init__(self, fname, url, suffix=suffix)
        self.session = streamlink.session.Streamlink({
            'stream-segment-timeout': 60,
            'hls-segment-queue-threshold': 10,
            'stream-segment-threads': 10
        })
        streamlink_plugins_dir = 'streamlink_plugins'
        if os.path.exists(streamlink_plugins_dir):
            self.session.plugins.load_path(streamlink_plugins_dir)

        self.is_download = False
        self.downloader = 'ffmpeg'

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
                ['streamlink', '--plugin-dir', 'streamlink_plugins', '-j', '--twitch-proxy-playlist',
                 'https://lb-eu3.cdn-perfprod.com,https://eu2.luminous.dev,', url],
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


class StreamGet(DownloadBase):
    def __init__(self, fname, url, suffix='mkv'):
        DownloadBase.__init__(self, fname, url, suffix=suffix)

        self.downloader = 'ffmpeg'

    async def acheck_stream(self, is_check=False):
        pass


@Plugin.download(regexp=r'(?:https?://)?(chaturbate\.com)/(?P<id>.*?)/')
class Chaturbate(Ytdlp):
    pass


@Plugin.download(regexp=r'(?:https?://)?(twitcasting\.tv)/(?P<id>.*?)/')
class Twitcasting(Ytdlp):
    pass


# https://17.live/en-US/profile/r/15519172
# https://17.live/en-US/live/15519172
@Plugin.download(regexp=r'(?:https?://)?(17\.live/[a-zA-z-]+/(profile/r|live))/(?P<id>.*?)')
class X17Live(Ytdlp):
    def __init__(self, fname, url, suffix='mkv'):
        super().__init__(fname, url, suffix)

        self.downloader = 'stream-gears'


# https://chzzk.naver.com/live/1b0561f3051c10a24b9d8ec9a6cb3374
@Plugin.download(regexp=r'(?:https?://)?(chzzk\.naver\.com)/live/(?P<id>.*?)')
class Chzzk(Ytdlp):
    def __init__(self, fname, url, suffix='mkv'):
        super().__init__(fname, url, suffix)

        self.downloader = 'streamlink'


@Plugin.download(regexp=r'(?:https?://)?(zh\.)?(stripchat\.com)/(?P<id>.*?)')
class Stripchat(StreamLink):
    pass


@Plugin.download(regexp=r'(?:https?://)?(play\.sooplive\.co\,kr)/(?P<id>.*?)')
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


@Plugin.download(regexp=r'(?:https?://)?(?:(?:www|go|m)\.)?twitch\.tv/(?P<id>[0-9_a-zA-Z]+)')
class Twitch(StreamLink):
    def __init__(self, fname, url, suffix='mkv'):
        StreamLink.__init__(self, fname, url, suffix=suffix)
        self.twitch_danmaku = config.get('twitch_danmaku', False)
        self.twitch_disable_ads = config.get('twitch_disable_ads', True)
        self.__proc = None

    def danmaku_init(self):
        if self.twitch_danmaku:
            self.danmaku = DanmakuClient(self.url, self.gen_download_filename())

    def close(self):
        try:
            if self.__proc is not None:
                self.__proc.terminate()
                self.__proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.__proc.kill()
        except:
            logger.exception(f'terminate {self.fname} failed')
        finally:
            self.__proc = None


@Plugin.download(regexp=r'(?:https?://)?kick\.com/(?P<id>[0-9_a-zA-Z]+)')
class Kick(StreamLink):
    pass


# https://www.tiktok.com/@ignobitaofficial/live
@Plugin.download(regexp=r'(?:https?://)?(?:(?:www|go|m)\.)?tiktok\.com/@(?P<id>[0-9_a-zA-Z.]+)(/live)?')
class Tiktok(StreamLink):
    def __init__(self, fname, url, suffix='mkv'):
        super().__init__(fname, url, suffix)
        self.is_download = False
        self.downloader = 'ffmpeg'


# https://www.pandalive.co.kr/live/play/queen486
@Plugin.download(regexp=r'(?:https?://)?(?:(?:www)\.)?pandalive\.co\.kr/live/play/(?P<id>[0-9_a-zA-Z]+)')
class Pandalive(StreamLink):
    pass



# https://www.sooplive.com/video/120240
@Plugin.download(regexp=r'(?:https?://)?(?:(?:www)\.)?sooplive\.com/video/(?P<id>[0-9]+)')
class SoopliveGlobalVod(StreamLink):
    def __init__(self, fname, url, suffix='mkv'):
        super().__init__(fname, url, suffix)
        self.is_download = True
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
                ['streamlink', '--plugin-dir', 'streamlink_plugins', '-j', url],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
        )

        info = json.loads(result)

        logger.info(info)

        self.raw_stream_url = self.url
        self.room_title = ''
        if type(info) is dict and info and 'metadata' in info and 'title' in info['metadata']:
            self.room_title = info['metadata']['title']

        return True


# https://www.sooplive.com/t3xture
@Plugin.download(regexp=r'(?:https?://)?(?:(?:www)\.)?sooplive\.com/(?P<id>[0-9_a-zA-Z]+)')
class SoopliveGlobal(SoopliveGlobalVod):
    def __init__(self, fname, url, suffix='mkv'):
        super().__init__(fname, url, suffix)
        self.is_download = False
        self.downloader = 'streamlink'



# https://weibo.com/l/wblive/p/show/1022:2321325160014053769290
@Plugin.download(regexp=r'(?:https?://)?(?:(?:www)\.)?weibo\.com/l/wblive/p/show/(?P<id>[0-9_a-zA-Z]+)')
class Weibo(StreamGet):
    async def acheck_stream(self, is_check=False):
        live = streamget.WeiboLiveStream()
        data = await live.fetch_web_stream_data(self.url)
        is_live = data.get('is_live')
        if not is_live:
            return False
        if 'play_url_list' not in data:
            return False
        if len(data['play_url_list']) == 0:
            return False
        streaminfo = data['play_url_list'][-1]
        if streaminfo.get("m3u8_url"):
            self.raw_stream_url = streaminfo.get("m3u8_url")
            if streaminfo.get("m3u8_url").endswith('.m3u8.m3u8'):
                self.raw_stream_url = self.raw_stream_url.replace('.m3u8.m3u8', '.m3u8')
        elif streaminfo.get("flv_url"):
            self.raw_stream_url = streaminfo.get("flv_url")
            if streaminfo.get("flv_url").endswith('.flv.flv'):
                self.raw_stream_url = self.raw_stream_url.replace('.flv.flv', '.flv')
        self.room_title = data['title'] if 'title' in data else ''
        return True


# https://3.cn/-2hJT570
@Plugin.download(regexp=r'(?:https?://)?3\.cn/(?P<id>[0-9_a-zA-Z-]+)')
class JDLive(StreamGet):
    async def acheck_stream(self, is_check=False):
        live = streamget.JDLiveStream()
        data = await live.fetch_web_stream_data(self.url)
        print(json.dumps(data, ensure_ascii=False))
        is_live = data.get('is_live')
        if not is_live:
            return False
        if 'flv_url' in data:
            self.raw_stream_url = data['flv_url']
        elif 'm3u8_url' in data:
            self.raw_stream_url = data['m3u8_url']
        else:
            self.raw_stream_url = data['record_url']
        self.room_title = ''
        return True


# http://xhslink.com/8MvrQdb
@Plugin.download(regexp=r'(?:https?://)?xhslink\.com/(?P<id>[0-9_a-zA-Z-]+)')
class XHSLive(StreamGet):
    async def acheck_stream(self, is_check=False):
        live = streamget.RedNoteLiveStream()
        data = await live.fetch_app_stream_data(self.url)
        print(json.dumps(data, ensure_ascii=False))
        is_live = data.get('is_live')
        if not is_live:
            return False
        if 'flv_url' in data:
            self.raw_stream_url = data['flv_url']
        elif 'm3u8_url' in data:
            self.raw_stream_url = data['m3u8_url']
        else:
            self.raw_stream_url = data['record_url']
        self.room_title = ''
        return True
