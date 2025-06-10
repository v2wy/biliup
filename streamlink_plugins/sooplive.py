"""
$description korean live-streaming platform
$url sooplive.com
$type live
$metadata id
$metadata author
$metadata title
$metadata category

"""
import logging
import re
from typing import Dict

from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream import HLSStream

log = logging.getLogger(__name__)


@pluginmatcher(
    re.compile(
        r"https?://(?:www\.)?sooplive\.com/video/(?P<vod_id>[^/?]+)"
    ),
)
@pluginmatcher(
    re.compile(
        r"https?://(?:www\.)?sooplive\.com/(?P<channel>[^/?]+)"
    ),
)
class SoopliveGlobal(Plugin):
    QUALITY_WEIGHTS: Dict[str, int] = {}

    def is_online(self, channel: str):
        url = f'https://www.sooplive.com/{channel}'
        res = self.session.http.get(url)
        if res.cookies.get('client-id') is None:
            return False, None, None, None, None
        self.session.http.headers.update({"Client-Id": res.cookies['client-id']})
        url = f'https://api.sooplive.com/v2/stream/info/{channel}'
        stream_info = self.session.http.get(url).json()
        if 'data' in stream_info and 'isStream' in stream_info['data'] and stream_info['data']['isStream']:
            data = stream_info['data']
            channel_info = self.session.http.get(f"https://api.sooplive.com/channel/info/{channel}").json()
            nickname = channel_info.get('streamerChannelInfo', {}).get('nickname', None)
            recentlyStreamCategoryInfoList = data.get("recentlyStreamCategoryInfoList", [])
            category = None
            if recentlyStreamCategoryInfoList:
                category = recentlyStreamCategoryInfoList[0].get("name", None)
            return True, data.get('idx', None), nickname, data.get('title', None), category
        return False, None, None, None, None

    def get_vod_info(self, vod_id):
        url = f'https://www.sooplive.com/video/{vod_id}'
        res = self.session.http.get(url)
        if res.cookies.get('client-id') is None:
            return None, None, None, None
        self.session.http.headers.update({"Client-Id": res.cookies['client-id']})
        url = f'https://api.sooplive.com/vod/info/{vod_id}'
        data = self.session.http.get(url).json()
        id = data.get('vodNo', vod_id)
        nickname = data.get('nickName', None)
        title = data.get('titleName', None)
        category = data.get('categoryName', None)
        return id, nickname, title, category

    def _get_streams(self):
        if self.match.lastgroup == 'vod_id':
            vod_id = self.match.group("vod_id")
            playlist_m3u8_url = f"https://global-media.sooplive.com/vod/{vod_id}/master.m3u8"
            playlist = HLSStream.parse_variant_playlist(self.session, url=playlist_m3u8_url)
            self.id, self.author, self.title, self.category = self.get_vod_info(vod_id)
            if self.id is None:
                log.error("This video is currently unavailable")
                return
            for k, stream in playlist.items():
                yield k, stream
            return
        channel = self.match.group("channel")
        is_online, self.id, self.author, self.title, self.category = self.is_online(channel)
        if not is_online:
            log.error("This stream is currently offline")
            return
        playlist_m3u8_url = f"https://global-media.sooplive.com/live/{channel}/master.m3u8"
        playlist = HLSStream.parse_variant_playlist(self.session, url=playlist_m3u8_url)
        for k, stream in playlist.items():
            yield k, stream


__plugin__ = SoopliveGlobal
