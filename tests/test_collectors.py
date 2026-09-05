import sys
import types
import unittest
from unittest.mock import patch

from ppiss.collectors import collect_now_playing


class FakeMPDClient:
    timeout = 0

    def connect(self, _host, _port):
        pass

    def status(self):
        return {"state": "play"}

    def currentsong(self):
        return {"file": "album/track.flac", "title": "Track", "artist": "Artist"}

    def readpicture(self, *args):
        if args != ("album/track.flac",):
            raise AssertionError("python-mpd2 binary helpers accept exactly one argument")
        return {"size": "3", "binary": b"art"}

    def albumart(self, *_args):
        return {}

    def close(self):
        pass


class CollectorTests(unittest.TestCase):
    def test_mpd_binary_helper_manages_offsets(self) -> None:
        fake_mpd = types.SimpleNamespace(
            MPDClient=FakeMPDClient,
            CommandError=RuntimeError,
            ConnectionError=ConnectionError,
            ProtocolError=RuntimeError,
        )
        with patch.dict(sys.modules, {"mpd": fake_mpd}), patch(
            "ppiss.collectors._playerctl", return_value=(None, None)
        ):
            playing, artwork = collect_now_playing("localhost", 6600)
        self.assertEqual(playing.title, "Track")
        self.assertEqual(artwork, b"art")


if __name__ == "__main__":
    unittest.main()
