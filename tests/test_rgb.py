import unittest

from ppiss.rgb import decode_colors, encode_colors


class RGBProtocolTests(unittest.TestCase):
    def test_rgb_frame_round_trip(self):
        fans = [[(fan * 20, led, 255 - led) for led in range(12)] for fan in range(3)]
        self.assertEqual(decode_colors(encode_colors(fans)), fans)

    def test_rgb_frame_rejects_wrong_led_count(self):
        with self.assertRaises(ValueError):
            encode_colors([[(0, 0, 0)]] * 3)


if __name__ == "__main__":
    unittest.main()
