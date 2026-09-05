from __future__ import annotations

import argparse
import io
import signal
import time

from .artwork_client import ArtworkClient
from .background import BackgroundRenderer, choose_logical_size
from .receiver import TelemetryReceiver
from .rgb import RGB_PORT, AnimationColorSender

DEVELOPMENT_SIZE = (800, 1280)


def _blit_text(surface, font, text: str, position, color=(255, 255, 255)) -> int:
    """Draw bitmap text without relying on per-pixel alpha support."""
    glyphs = font.render(text, False, color)
    glyphs.set_colorkey((0, 0, 0))
    surface.blit(glyphs, position)
    return glyphs.get_width()


def _metric_rows(telemetry) -> list[tuple[str, str, str]]:
    if not telemetry:
        return [("telemetry", "no signal", ""), ("udp port", "45891", "")]
    cpu_temp = f"{telemetry.cpu_temp_c:.1f} c" if telemetry.cpu_temp_c is not None else "--"
    rows = [
        ("cpu", f"{telemetry.cpu_percent:.1f} %", cpu_temp),
    ]
    if telemetry.gpus:
        for index, gpu in enumerate(telemetry.gpus):
            load = f"{gpu.utilization_percent:.1f} %" if gpu.utilization_percent is not None else "--"
            temp = f"{gpu.temperature_c:.1f} c" if gpu.temperature_c is not None else "--"
            rows.append((f"gpu{index}", load, temp))
    elif telemetry.gpu_percent is not None:
        rows.append(("gpu", f"{telemetry.gpu_percent:.1f} %", ""))
    rows.append(
        (
            "memory",
            f"{telemetry.memory_percent:.1f} %",
            f"{telemetry.memory_used_gb:.1f} / {telemetry.memory_total_gb:.1f} gb",
        )
    )
    rows.extend(
        (
            f"disk{index}",
            f"{disk.percent:.1f} %",
            f"{disk.used_gb:.1f} / {disk.total_gb:.1f} gb",
        )
        for index, disk in enumerate(telemetry.disks)
    )
    return rows


def draw_overlay(pg, surface, telemetry, age: float, font, small_font) -> int:
    width = surface.get_width()
    margin = max(16, width // 32)
    rows = _metric_rows(telemetry)
    row_height = small_font.get_linesize() + 8
    header_height = font.get_linesize() + 34
    max_panel_height = surface.get_height() // 2
    max_rows = max(2, (max_panel_height - header_height - 12) // row_height)
    rows = rows[:max_rows]
    panel_height = header_height + len(rows) * row_height + 12
    panel_width = width - margin * 2
    # Darken the existing pixels in place. This looks like translucent black but avoids
    # intermediate alpha surfaces, which some direct KMS/SDL combinations flatten.
    surface.fill(
        (105, 105, 105),
        (margin, margin, panel_width, panel_height),
        special_flags=pg.BLEND_RGB_MULT,
    )

    text_color = (255, 255, 255)
    padding = max(12, margin // 2)
    hostname = telemetry.hostname.lower() if telemetry else "ppiss"
    hostname_x = margin + padding
    hostname_width = _blit_text(surface, font, hostname, (hostname_x, margin + 12), text_color)
    linked = bool(telemetry and age < 4)
    status = "●" if linked and int(time.monotonic() * 2) % 2 == 0 else ("" if linked else "○")
    if status:
        _blit_text(surface, small_font, status, (hostname_x + hostname_width + padding, margin + 18))
    table_top = margin + header_height
    label_x = margin + padding
    column_gap = small_font.size("   ")[0]
    label_width = max(small_font.size(label)[0] for label, _, _ in rows)
    load_width = max(small_font.size(load)[0] for _, load, _ in rows)
    load_x = label_x + label_width + column_gap
    temperature_x = load_x + load_width + column_gap
    for index, (label, load, temperature) in enumerate(rows):
        y = table_top + index * row_height
        _blit_text(surface, small_font, label, (label_x, y + 4), text_color)
        _blit_text(surface, small_font, load, (load_x, y + 4), text_color)
        if temperature:
            _blit_text(surface, small_font, temperature, (temperature_x, y + 4), text_color)
    return margin + panel_height


def draw_now_playing(pg, surface, playing, artwork, font, small_font, overlay_bottom: int) -> None:
    margin = max(16, surface.get_width() // 32)
    top = overlay_bottom + margin
    available = surface.get_height() - top - margin
    art_size = min(surface.get_width() - margin * 2, max(0, available - 150))
    if artwork and art_size:
        image = pg.transform.smoothscale(artwork, (art_size, art_size))
        surface.blit(image, ((surface.get_width() - art_size) // 2, top))
    text_top = top + (art_size if artwork else 20) + 24
    title = playing.title.lower() if len(playing.title) < 34 else playing.title[:31].lower() + "..."
    artist = playing.artist.lower() if len(playing.artist) < 48 else playing.artist[:45].lower() + "..."
    _blit_text(surface, font, title, (margin, text_top))
    _blit_text(surface, small_font, artist, (margin, text_top + font.get_height()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PPISS Raspberry Pi generative display")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=45891)
    parser.add_argument("--windowed", action="store_true", help="Development window instead of fullscreen")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--rgb-port", type=int, default=RGB_PORT)
    parser.add_argument("--rgb-rate", type=float, default=10.0)
    parser.add_argument("--no-rgb", action="store_true", help="Disable animation colour streaming")
    args = parser.parse_args()

    try:
        import pygame as pg
    except ImportError as exc:
        raise SystemExit("Install display dependencies: pip install 'ppiss[pi]'") from exc

    pg.init()
    flags = 0 if args.windowed else pg.FULLSCREEN
    try:
        screen = pg.display.set_mode(DEVELOPMENT_SIZE if args.windowed else (0, 0), flags)
    except pg.error as exc:
        raise SystemExit(f"Could not initialize the KMS display: {exc}") from exc
    pg.display.set_caption("PPISS")
    pg.mouse.set_visible(args.windowed)
    signal.signal(signal.SIGTERM, lambda *_: pg.event.post(pg.event.Event(pg.QUIT)))
    display_size = screen.get_size()
    background = BackgroundRenderer(pg, choose_logical_size(display_size))
    mono_path = pg.font.match_font("dejavusansmono") or pg.font.match_font("monospace")
    font = pg.font.Font(mono_path, max(30, min(58, display_size[0] // 15)))
    small_font = pg.font.Font(mono_path, max(20, min(34, display_size[0] // 24)))
    debug_font = pg.font.Font(mono_path, 18) if args.windowed else None
    clock = pg.time.Clock()
    receiver = TelemetryReceiver(args.bind, args.port)
    receiver.start()
    rgb_sender = None if args.no_rgb else AnimationColorSender(args.rgb_port, args.rgb_rate)
    artwork_client = ArtworkClient()
    artwork_id = None
    artwork_surface = None
    started = time.monotonic()

    try:
        running = True
        while running:
            elapsed = time.monotonic() - started
            for event in pg.event.get():
                running = not (event.type == pg.QUIT or (event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE))
                if args.windowed and event.type == pg.KEYDOWN:
                    if event.key == pg.K_RIGHT:
                        background.next(elapsed)
                    elif event.key == pg.K_LEFT:
                        background.next(elapsed, -1)
                    elif event.key == pg.K_r:
                        background.random_preset(elapsed)
                    elif event.key in (pg.K_p, pg.K_SPACE):
                        background.toggle_pause(elapsed)
            background_frame = background.render(elapsed)
            if rgb_sender:
                rgb_sender.update(background_frame, receiver.peer_host, time.monotonic())
            pg.transform.scale(background_frame, display_size, screen)
            telemetry, age = receiver.snapshot()
            overlay_bottom = draw_overlay(pg, screen, telemetry, age, font, small_font)
            if telemetry and telemetry.now_playing and telemetry.now_playing.state == "playing":
                playing = telemetry.now_playing
                artwork_client.request(playing.artwork_id, playing.artwork_url)
                ready = artwork_client.take()
                if ready:
                    try:
                        artwork_id, artwork_surface = ready[0], pg.image.load(io.BytesIO(ready[1])).convert()
                    except pg.error:
                        artwork_surface = None
                draw_now_playing(
                    pg, screen, playing,
                    artwork_surface if artwork_id == playing.artwork_id else None,
                    font, small_font, overlay_bottom,
                )
            if args.windowed:
                label = f"{background.preset_name.lower()}  [←/→ preset, r random, p pause]"
                debug_y = display_size[1] - debug_font.get_linesize() - 10
                _blit_text(screen, debug_font, label, (10, debug_y))
            pg.display.flip()
            clock.tick(max(1, args.fps))
    finally:
        if rgb_sender:
            rgb_sender.close()
        receiver.stop()
        pg.quit()


if __name__ == "__main__":
    main()
