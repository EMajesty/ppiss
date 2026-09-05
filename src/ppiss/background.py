"""Original low-resolution battle-background-style procedural renderer."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

Color = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class Wave:
    amplitude: float
    frequency: float
    speed: float
    phase: float = 0.0
    amplitude_evolution: float = 0.0
    frequency_evolution: float = 0.0
    evolution_speed: float = 0.1

    def offset(self, y: float, time_s: float) -> float:
        amplitude = self.amplitude + self.amplitude_evolution * math.sin(
            time_s * self.evolution_speed + self.phase
        )
        frequency = self.frequency + self.frequency_evolution * math.sin(
            time_s * self.evolution_speed * 0.73 + self.phase
        )
        return amplitude * math.sin(frequency * y + self.speed * time_s + self.phase)


@dataclass(frozen=True, slots=True)
class DistortionEffect:
    mode: str
    waves: tuple[Wave, ...] = ()
    interlace_group: int = 2
    compression: float = 1.0
    compression_evolution: float = 0.0
    compression_speed: float = 0.2

    def horizontal_offset(self, y: int, time_s: float) -> int:
        offset = sum(wave.offset(y, time_s) for wave in self.waves)
        if self.mode == "interlaced" and (y // max(1, self.interlace_group)) % 2:
            offset = -offset
        return round(offset)

    def source_y(self, y: int, height: int, time_s: float) -> int:
        scale = self.compression + self.compression_evolution * math.sin(
            time_s * self.compression_speed
        )
        scale = max(0.25, scale)
        center = (height - 1) / 2
        mapped = center + (y - center) / scale
        mapped += sum(wave.offset(y, time_s) for wave in self.waves)
        return round(mapped)


@dataclass(frozen=True, slots=True)
class LayerSpec:
    pattern: str
    palette: tuple[Color, ...]
    effect: DistortionEffect
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    palette_speed: float = 0.5
    opacity: int = 255
    blend: str = "normal"


@dataclass(frozen=True, slots=True)
class Preset:
    name: str
    layers: tuple[LayerSpec, LayerSpec]


PALETTES: dict[str, tuple[Color, ...]] = {
    "ultraviolet": ((2, 1, 10), (12, 5, 38), (30, 10, 75), (66, 15, 100), (120, 20, 105), (205, 24, 115)),
    "crimson": ((3, 1, 4), (24, 2, 8), (55, 4, 12), (92, 5, 15), (142, 10, 20), (205, 25, 32)),
    "night": ((1, 2, 9), (3, 6, 28), (5, 12, 55), (10, 24, 88), (25, 38, 118), (64, 48, 135)),
    "bruise": ((4, 2, 8), (18, 7, 28), (43, 13, 50), (75, 22, 72), (112, 34, 91), (160, 55, 110)),
    "rust": ((5, 2, 3), (30, 8, 7), (62, 15, 12), (100, 24, 18), (144, 39, 25), (188, 62, 38)),
}


def build_presets() -> tuple[Preset, ...]:
    horizontal = lambda *waves: DistortionEffect("horizontal", waves)
    interlaced = lambda group, *waves: DistortionEffect("interlaced", waves, group)
    vertical = lambda compression, evolution, *waves: DistortionEffect(
        "vertical", waves, compression=compression,
        compression_evolution=evolution, compression_speed=0.32,
    )
    return (
        Preset("Liquid Signal", (
            LayerSpec("rings", PALETTES["ultraviolet"], horizontal(Wave(10, .055, 1.0), Wave(4, .14, -.55, 1.2)), .8, .25, .6),
            LayerSpec("diamonds", PALETTES["crimson"], vertical(1.0, .22, Wave(5, .035, .45)), -.35, .7, .35, 105, "add"),
        )),
        Preset("Interference Engine", (
            LayerSpec("diagonal", PALETTES["night"], interlaced(2, Wave(15, .075, 1.8), Wave(5, .018, -.7)), 1.2, .15, .8),
            LayerSpec("cells", PALETTES["ultraviolet"], horizontal(Wave(8, .11, -1.25)), -.65, .4, .45, 145, "add"),
        )),
        Preset("Breathing Well", (
            LayerSpec("radial", PALETTES["rust"], vertical(.9, .35, Wave(4, .06, .7)), .15, .35, .3),
            LayerSpec("rings", PALETTES["night"], interlaced(3, Wave(7, .045, -.8)), -.45, -.2, .5, 110, "add"),
        )),
        Preset("Diagonal Drift", (
            LayerSpec("diagonal", PALETTES["bruise"], horizontal(Wave(12, .035, .65), Wave(3, .17, 1.4)), .95, .5, .4),
            LayerSpec("diamonds", PALETTES["crimson"], vertical(1.05, .16, Wave(3, .08, -.5)), -.25, .65, .7, 100, "add"),
        )),
        Preset("Quiet Geometry", (
            LayerSpec("diamonds", PALETTES["night"], horizontal(Wave(5, .04, .35, amplitude_evolution=2)), .25, .15, .25),
            LayerSpec("cells", PALETTES["bruise"], interlaced(4, Wave(4, .07, -.4)), -.2, .2, .2, 95, "add"),
        )),
    )


def choose_logical_size(display_size: tuple[int, int]) -> tuple[int, int]:
    width, height = display_size
    for scale in (5, 4, 3):
        if width % scale == 0 and height % scale == 0 and width // scale >= 128:
            return width // scale, height // scale
    return max(128, width // 4), max(192, height // 4)


def _pattern_indices(name: str, size: int = 128, colors: int = 6) -> list[list[int]]:
    center = (size - 1) / 2
    tau = math.tau
    result: list[list[int]] = []
    for y in range(size):
        row = []
        for x in range(size):
            if name == "radial":
                dx = min(abs(x - center), size - abs(x - center))
                dy = min(abs(y - center), size - abs(y - center))
                value = int(math.hypot(dx, dy) / 7)
            elif name == "rings":
                dx = min(abs(x - center), size - abs(x - center))
                dy = min(abs(y - center), size - abs(y - center)) * .72
                value = int(math.hypot(dx, dy) / 5)
            elif name == "diamonds":
                value = (abs((x % 64) - 32) + abs((y % 64) - 32)) // 8
            elif name == "diagonal":
                waves = math.sin(tau * (x + y * 2) / 128)
                waves += .45 * math.sin(tau * (x - y) / 64)
                value = int((waves + 1.45) / 2.9 * colors)
            else:  # chunky deterministic cellular field
                cells = math.sin(tau * x / 64) + math.sin(tau * y / 64)
                cells += .6 * math.sin(tau * (x + y) / 128)
                value = int((cells + 2.6) / 5.2 * colors)
            row.append(value % colors)
        result.append(row)
    return result


class BackgroundLayer:
    def __init__(self, pg, size: tuple[int, int], spec: LayerSpec) -> None:
        self.pg, self.size, self.spec = pg, size, spec
        self.tile_size = 128
        indices = _pattern_indices(spec.pattern, self.tile_size, len(spec.palette))
        self.variants = []
        self.palette_substeps = 4
        tiled_width = size[0] + self.tile_size
        variant_count = len(spec.palette) * self.palette_substeps
        for step in range(variant_count):
            phase, substep = divmod(step, self.palette_substeps)
            mix = substep / self.palette_substeps
            tile = pg.Surface((self.tile_size, self.tile_size))
            pixels = pg.PixelArray(tile)
            mapped = []
            for index in range(len(spec.palette)):
                first = spec.palette[(index + phase) % len(spec.palette)]
                second = spec.palette[(index + phase + 1) % len(spec.palette)]
                color = tuple(round(a + (b - a) * mix) for a, b in zip(first, second, strict=True))
                mapped.append(tile.map_rgb(color))
            for y, row in enumerate(indices):
                for x, index in enumerate(row):
                    pixels[x, y] = mapped[index]
            del pixels
            repeated = pg.Surface((tiled_width, self.tile_size))
            for x in range(0, tiled_width, self.tile_size):
                repeated.blit(tile, (x, 0))
            self.variants.append(repeated)
        self.surface = pg.Surface(size)
        self.surface.set_alpha(spec.opacity)

    def render(self, time_s: float):
        width, height = self.size
        phase = int(time_s * self.spec.palette_speed * self.palette_substeps)
        source = self.variants[phase % len(self.variants)]
        effect = self.spec.effect
        for y in range(height):
            source_y = effect.source_y(y, height, time_s) if effect.mode == "vertical" else y
            source_y = int(source_y + time_s * self.spec.scroll_y) % self.tile_size
            offset = effect.horizontal_offset(y, time_s) if effect.mode != "vertical" else 0
            source_x = int(offset + time_s * self.spec.scroll_x) % self.tile_size
            self.surface.blit(source, (0, y), (source_x, source_y, width, 1))
        return self.surface


class BackgroundRenderer:
    def __init__(self, pg, size: tuple[int, int], preset_seconds: float = 32.0) -> None:
        self.pg, self.size = pg, size
        self.presets = build_presets()
        self.preset_seconds = preset_seconds
        self.index = 0
        self.started_at = 0.0
        self.paused = False
        self.pause_started = 0.0
        self.paused_total = 0.0
        self.rng = random.Random(0x50504953)
        self.canvas = pg.Surface(size)
        self.previous_canvas = pg.Surface(size)
        self._preset_layers = tuple(self._make_layers(preset) for preset in self.presets)
        self._layers = self._preset_layers[0]
        self._previous_layers = None
        self.transition_started = -10.0
        self.transition_seconds = 5.0

    @property
    def preset_name(self) -> str:
        return self.presets[self.index].name

    def _make_layers(self, preset: Preset):
        return tuple(BackgroundLayer(self.pg, self.size, spec) for spec in preset.layers)

    def _effective_time(self, time_s: float) -> float:
        current = self.pause_started if self.paused else time_s
        return current - self.paused_total

    def _select_at(self, index: int, effective_time: float) -> None:
        self._previous_layers = self._layers
        self.index = index % len(self.presets)
        self._layers = self._preset_layers[self.index]
        self.started_at = effective_time
        self.transition_started = effective_time

    def select(self, index: int, time_s: float) -> None:
        self._select_at(index, self._effective_time(time_s))

    def next(self, time_s: float, direction: int = 1) -> None:
        self.select(self.index + direction, time_s)

    def random_preset(self, time_s: float) -> None:
        choices = [index for index in range(len(self.presets)) if index != self.index]
        self.select(self.rng.choice(choices), time_s)

    def toggle_pause(self, time_s: float) -> None:
        if self.paused:
            self.paused_total += time_s - self.pause_started
        else:
            self.pause_started = time_s
        self.paused = not self.paused

    def render(self, time_s: float):
        effective = self._effective_time(time_s)
        if effective - self.started_at >= self.preset_seconds:
            self._select_at(self.index + 1, effective)
        self._compose(self._layers, effective, self.canvas)
        transition = (effective - self.transition_started) / self.transition_seconds
        if self._previous_layers and transition < 1:
            self._compose(self._previous_layers, effective, self.previous_canvas)
            progress = max(0, transition)
            eased = progress * progress * (3 - 2 * progress)
            self.previous_canvas.set_alpha(round(255 * (1 - eased)))
            self.canvas.blit(self.previous_canvas, (0, 0))
            self.previous_canvas.set_alpha(None)
        elif self._previous_layers:
            self._previous_layers = None
        return self.canvas

    def _compose(self, layers, time_s: float, target) -> None:
        first, second = layers
        target.blit(first.render(time_s), (0, 0))
        blend = self.pg.BLEND_RGB_ADD if second.spec.blend == "add" else 0
        target.blit(second.render(time_s), (0, 0), special_flags=blend)
