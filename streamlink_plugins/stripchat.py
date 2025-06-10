"""
$description Chinese live-streaming platform
$url stripchat.com
$type live
$metadata id
$metadata author
$metadata title
"""
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
class Striphat(Plugin):
    QUALITY_WEIGHTS: Dict[str, int] = {}

    @classmethod
    def stream_weight(cls, key):
        weight = cls.QUALITY_WEIGHTS.get(key)
        if weight:
            return weight, key

        return super().stream_weight(key)

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


__plugin__ = Striphat
