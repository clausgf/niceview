"""
Regenerate the README screenshots with Playwright + Chromium.

Usage:
    uv sync --group screenshots
    uv run playwright install chromium   # once, to fetch the browser
    uv run python docs/screenshots/capture.py

Starts docs/screenshots/apps.py as a subprocess, captures:
    docs/img/hero.png       — a styled ModelForm (varied widget types)
    docs/img/grid.png       — an EditGridWrapper with CRUD buttons
    docs/img/drilldown.gif  — the ModelList -> detail drill-down navigation
"""
import io
import socket
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
IMG = HERE.parent / 'img'
APP = HERE / 'apps.py'
PORT = 8137
BASE = f'http://127.0.0.1:{PORT}'


def _wait_port(port: int, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), 0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([sys.executable, str(APP)], cwd=str(HERE))
    try:
        if not _wait_port(PORT):
            raise RuntimeError('screenshot app did not start')
        time.sleep(1.0)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(device_scale_factor=2)
            page = ctx.new_page()

            # --- hero: styled ModelForm ---
            page.set_viewport_size({'width': 560, 'height': 1024})
            page.goto(f'{BASE}/hero')
            page.wait_for_selector('.shot-card')
            page.wait_for_timeout(800)
            page.locator('.shot-card').screenshot(path=str(IMG / 'hero.png'))
            print('wrote', IMG / 'hero.png')

            # --- grid: EditGridWrapper ---
            page.set_viewport_size({'width': 980, 'height': 680})
            page.goto(f'{BASE}/grid')
            page.wait_for_selector('.ag-root-wrapper')
            page.wait_for_timeout(1000)
            page.locator('.shot-card').screenshot(path=str(IMG / 'grid.png'))
            print('wrote', IMG / 'grid.png')

            # --- drilldown: animated GIF (list -> detail -> back) ---
            page.set_viewport_size({'width': 440, 'height': 520})
            page.goto(f'{BASE}/drilldown')
            page.wait_for_selector('.shot-card')
            page.wait_for_timeout(800)
            clip = {'x': 0, 'y': 0, 'width': 440, 'height': 400}
            frames: list[Image.Image] = []
            durations: list[int] = []

            def snap(hold: int) -> None:
                frames.append(Image.open(io.BytesIO(page.screenshot(clip=clip))).convert('RGB'))
                durations.append(hold)

            snap(1100)                                   # list view, held
            page.get_by_text('api-gateway').first.click()
            for _ in range(6):                           # slide into detail
                page.wait_for_timeout(45)
                snap(70)
            page.wait_for_timeout(350)
            snap(1700)                                   # detail view, held
            page.get_by_text('arrow_back').first.click()
            for _ in range(6):                           # slide back to list
                page.wait_for_timeout(45)
                snap(70)
            snap(500)

            # downscale + quantize to keep the GIF small
            target_w = 380
            small = [f.resize((target_w, round(f.height * target_w / f.width))) for f in frames]
            small = [im.quantize(colors=128, method=Image.MEDIANCUT) for im in small]
            small[0].save(
                IMG / 'drilldown.gif', save_all=True, append_images=small[1:],
                duration=durations, loop=0, disposal=2, optimize=True,
            )
            print('wrote', IMG / 'drilldown.gif', f'({len(small)} frames)')

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    main()
