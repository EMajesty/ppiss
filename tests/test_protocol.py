import json
import unittest

from ppiss.protocol import GPU, NowPlaying, Telemetry, decode, encode


def sample() -> Telemetry:
    return Telemetry(
        "workstation", 42.5, 61.0, gpu_percent=78, timestamp=1234,
        gpus=(GPU("GPU A", 72, 61), GPU("GPU B", None, 44)),
        now_playing=NowPlaying(
            "spotify", "playing", "Track", "Artist", "Album", "abc",
            "http://10.55.0.1:45892/art/abc",
        ),
    )


class ProtocolTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        self.assertEqual(decode(encode(sample())), sample())

    def test_rejects_unknown_version(self) -> None:
        packet = json.dumps({"payload": {"v": 99, "stats": {}}}).encode()
        with self.assertRaisesRegex(ValueError, "version"):
            decode(packet)


if __name__ == "__main__":
    unittest.main()
