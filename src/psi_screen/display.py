from __future__ import annotations

import argparse
import math
import os
import random
import time

from .receiver import TelemetryReceiver

LOGICAL_SIZE = (200, 320)
DISPLAY_SIZE = (800, 1280)


def _palette(t: float) -> list[tuple[int, int, int]]:
    phases = (0.0, 2.1, 4.2)
    return [
        tuple(int(104 + 100 * math.sin(t * 0.17 + phase + shift)) for shift in phases)
        for phase in (0.0, 1.7, 3.4, 5.1)
    ]


def draw_background(pg, canvas, t: float) -> None:
    width, height = canvas.get_size()
    colors = _palette(t)
    canvas.fill(colors[0])
    # Sine-warped bands and orbiting blobs give a psychedelic, battle-screen-like mood.
    for y in range(0, height, 3):
        wave = math.sin(y * 0.09 + t * 1.3) + math.sin(y * 0.027 - t * 0.8)
        color = colors[int((wave + 2) / 4 * (len(colors) - 1))]
        offset = int(12 * math.sin(y * 0.04 + t))
        pg.draw.rect(canvas, color, (offset - 12, y, width + 24, 2))
    for index in range(9):
        angle = t * (0.12 + index * 0.013) + index * 0.7
        x = int(width / 2 + math.sin(angle * 1.7) * width * 0.55)
        y = int(height / 2 + math.cos(angle) * height * 0.5)
        radius = 8 + int(9 * (1 + math.sin(t + index)))
        pg.draw.circle(canvas, colors[(index + 1) % 4], (x, y), radius, 2)
    # Sparse deterministic sparkles; seeded per frame to avoid accumulating state.
    rng = random.Random(int(t * 7))
    for _ in range(25):
        canvas.set_at((rng.randrange(width), rng.randrange(height)), (245, 245, 220))


def draw_overlay(pg, surface, telemetry, age: float, font, small_font) -> None:
    width = surface.get_width()
    panel = pg.Surface((width - 48, 270), pg.SRCALPHA)
    panel.fill((4, 5, 12, 205))
    pg.draw.rect(panel, (236, 235, 214), panel.get_rect(), width=4, border_radius=10)
    surface.blit(panel, (24, 28))

    status = "LINKED" if telemetry and age < 4 else "WAITING FOR PC"
    color = (118, 255, 182) if status == "LINKED" else (255, 208, 92)
    surface.blit(small_font.render(status, True, color), (50, 48))
    if not telemetry:
        surface.blit(font.render("NO SIGNAL", True, (245, 245, 225)), (50, 105))
        surface.blit(small_font.render("UDP :45891", True, (180, 185, 200)), (50, 178))
        return

    surface.blit(font.render(telemetry.hostname.upper(), True, (245, 245, 225)), (50, 88))
    fields = [
        f"CPU  {telemetry.cpu_percent:5.1f}%",
        f"RAM  {telemetry.memory_percent:5.1f}%",
    ]
    if telemetry.gpu_percent is not None:
        fields.append(f"GPU  {telemetry.gpu_percent:5.1f}%")
    if telemetry.cpu_temp_c is not None:
        fields.append(f"TEMP {telemetry.cpu_temp_c:5.1f} C")
    for index, label in enumerate(fields[:3]):
        surface.blit(small_font.render(label, True, (220, 225, 235)), (50 + (index % 2) * 340, 170 + (index // 2) * 48))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Raspberry Pi generative status display")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=45891)
    parser.add_argument("--secret", default=os.getenv("PSI_SECRET", ""))
    parser.add_argument("--windowed", action="store_true", help="Development window instead of fullscreen")
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()

    try:
        import pygame as pg
    except ImportError as exc:
        raise SystemExit("Install display dependencies: pip install 'psi-screen[pi]'") from exc

    pg.init()
    flags = 0 if args.windowed else pg.FULLSCREEN
    screen = pg.display.set_mode(DISPLAY_SIZE, flags)
    pg.display.set_caption("psi-screen")
    pg.mouse.set_visible(args.windowed)
    canvas = pg.Surface(LOGICAL_SIZE)
    font = pg.font.Font(None, 62)
    small_font = pg.font.Font(None, 38)
    clock = pg.time.Clock()
    receiver = TelemetryReceiver(args.bind, args.port, args.secret)
    receiver.start()
    started = time.monotonic()

    try:
        running = True
        while running:
            for event in pg.event.get():
                running = not (event.type == pg.QUIT or (event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE))
            draw_background(pg, canvas, time.monotonic() - started)
            pg.transform.scale(canvas, DISPLAY_SIZE, screen)
            telemetry, age = receiver.snapshot()
            draw_overlay(pg, screen, telemetry, age, font, small_font)
            pg.display.flip()
            clock.tick(max(1, args.fps))
    finally:
        receiver.stop()
        pg.quit()


if __name__ == "__main__":
    main()

