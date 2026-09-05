import math
import unittest

from ppiss.background import DistortionEffect, Wave, build_presets, choose_logical_size


class BackgroundMathTests(unittest.TestCase):
    def test_wave_offset_is_deterministic(self) -> None:
        wave = Wave(8, 0.25, 1.5, 0.3)
        expected = 8 * math.sin(0.25 * 12 + 1.5 * 2 + 0.3)
        self.assertAlmostEqual(wave.offset(12, 2), expected)
        self.assertEqual(wave.offset(12, 2), wave.offset(12, 2))

    def test_interlaced_groups_reverse_direction(self) -> None:
        effect = DistortionEffect("interlaced", (Wave(10, 0, 0, math.pi / 2),), 2)
        self.assertEqual(effect.horizontal_offset(0, 0), 10)
        self.assertEqual(effect.horizontal_offset(2, 0), -10)

    def test_vertical_compression_maps_rows(self) -> None:
        compressed = DistortionEffect("vertical", compression=2)
        self.assertLess(abs(compressed.source_y(0, 100, 0) - 50), 50)

    def test_presets_have_two_layers_and_all_modes(self) -> None:
        presets = build_presets()
        self.assertGreaterEqual(len(presets), 4)
        self.assertTrue(all(len(preset.layers) == 2 for preset in presets))
        modes = {layer.effect.mode for preset in presets for layer in preset.layers}
        self.assertEqual(modes, {"horizontal", "interlaced", "vertical"})

    def test_logical_size_prefers_integer_scale(self) -> None:
        self.assertEqual(choose_logical_size((800, 1280)), (160, 256))


if __name__ == "__main__":
    unittest.main()
