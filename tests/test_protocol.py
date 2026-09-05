import json
import unittest

from ppiss.protocol import Telemetry, decode, encode


def sample() -> Telemetry:
    return Telemetry("workstation", 42.5, 61.0, gpu_percent=78, timestamp=1234)


class ProtocolTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        self.assertEqual(decode(encode(sample())), sample())

    def test_signed_round_trip(self) -> None:
        self.assertEqual(decode(encode(sample(), "secret"), "secret"), sample())

    def test_rejects_wrong_secret(self) -> None:
        with self.assertRaisesRegex(ValueError, "signature"):
            decode(encode(sample(), "right"), "wrong")

    def test_rejects_unknown_version(self) -> None:
        packet = json.dumps({"payload": {"v": 99, "stats": {}}}).encode()
        with self.assertRaisesRegex(ValueError, "version"):
            decode(packet)


if __name__ == "__main__":
    unittest.main()
