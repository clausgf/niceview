"""
Screenshot every numbered example for the documentation site.

Usage:
    uv sync --group screenshots
    uv run playwright install chromium        # once, to fetch the browser
    uv run python docs/screenshots/capture_examples.py            # all of them
    uv run python docs/screenshots/capture_examples.py 16 18      # only these

Each example is started headlessly (see _serve_example.py), opened at '/', stripped of the
leading docstring — the page prints it with ui.markdown, and the documentation page around the
screenshot already says the same thing — and photographed from below the separator down. The
images land in docs/img/examples/ and are picked up by docs/gen_example_pages.py.

The examples that persist something write it where they always do (example_*.json,
example_notes/, example_sqlmodel.db in the project root, all git-ignored). A capture run
therefore leaves the same files behind as running the examples by hand.
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
EXAMPLES = ROOT / 'examples'
OUT = ROOT / 'docs' / 'img' / 'examples'
RUNNER = HERE / '_serve_example.py'
PORT = 8138

WIDTH = 1000
"""Viewport width. Wide enough for the two-column examples, narrow enough to stay readable
when the site scales the image down to the content column."""

MAX_HEIGHT = 1400
"""Cap for a very long page (02_field_types shows every widget type there is). Cutting the
image is better than a screenshot no one can take in at a glance."""

# What to wait for before the shot: a page whose interesting part arrives late says so here.
# Everything else is covered by the default (the content div plus a settling pause).
READY_SELECTOR: dict[str, str] = {
    '05_grid': '.ag-root-wrapper',
    '07_sqlmodel': '.ag-root-wrapper',
    '08_reactive_grid': '.ag-root-wrapper',
    '06_edit_wrapper': '.ag-root-wrapper',
}

# The docstring is the page's own introduction; the documentation page repeats it around the
# image, so the shot starts below it. Removing it in the browser keeps the examples themselves
# free of any screenshot machinery.
STRIP_DOCSTRING = """
() => {
  const content = document.querySelector('.nicegui-content');
  if (!content) return;
  const first = content.firstElementChild;
  if (!first || !first.classList.contains('nicegui-markdown')) return;
  const next = first.nextElementSibling;
  first.remove();
  if (next && (next.tagName === 'HR' || next.classList.contains('nicegui-separator'))) next.remove();
}
"""


# Two examples start from an empty store, which is the right thing when a reader runs them and
# the wrong thing for a picture: a list example whose picture shows no list says nothing. These
# write the same files the examples would write themselves, before they start. Everything else
# carries its data in the source.
FIXTURES: dict[str, dict[str, str]] = {
    '12_card_list': {
        'example_webhooks.json': json.dumps([
            {'name': 'deploy-notify', 'method': 'POST', 'url': 'https://hooks.example.com/deploy'},
            {'name': 'nightly-sync', 'method': 'PUT', 'url': 'https://api.example.com/sync'},
            {'name': 'health-check', 'method': 'GET', 'url': 'http://status.example.com/live'},
        ], indent=2),
    },
    '13_directory_drilldown': {
        'example_notes/shopping.json': json.dumps({'text': 'Milk, bread, coffee beans.'}, indent=2),
        'example_notes/meeting.json': json.dumps({'text': 'Ship 0.20, then look at the grid filters.'}, indent=2),
        'example_notes/ideas.json': json.dumps({'text': 'A card grid for collections, responsive.'}, indent=2),
    },
}


def _write_fixtures(stem: str) -> None:
    for name, content in FIXTURES.get(stem, {}).items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def _wait_port(port: int, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), 0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _capture(page, example: Path) -> bool:
    """Photograph one running example. Returns False if the page never became usable."""
    try:
        page.goto(f'http://127.0.0.1:{PORT}/', wait_until='networkidle', timeout=20000)
        page.wait_for_selector('.nicegui-content', timeout=15000)
        selector = READY_SELECTOR.get(example.stem)
        if selector:
            page.wait_for_selector(selector, timeout=15000)
        page.wait_for_timeout(1200)  # Quasar transitions, lazily rendered grids, async options
        page.evaluate(STRIP_DOCSTRING)
        page.wait_for_timeout(200)

        box = page.locator('.nicegui-content').bounding_box()
        if box is None or box['height'] < 1:
            print(f'  {example.stem}: nothing rendered')
            return False
        clip = {'x': box['x'], 'y': box['y'], 'width': box['width'],
                'height': min(box['height'], MAX_HEIGHT)}
        page.screenshot(path=str(OUT / f'{example.stem}.png'), clip=clip)
        print(f'  wrote docs/img/examples/{example.stem}.png '
              f"({round(clip['width'])}x{round(clip['height'])})")
        return True
    except PlaywrightError as e:
        print(f'  {example.stem}: {str(e).splitlines()[0]}')
        return False


def main(only: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    examples = sorted(p for p in EXAMPLES.glob('[0-9]*.py'))
    if only:
        examples = [p for p in examples if any(p.stem.startswith(prefix) for prefix in only)]
    if not examples:
        print('no matching examples')
        return 1

    failed: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': WIDTH, 'height': 900},
                                      device_scale_factor=2)
        page = context.new_page()
        for example in examples:
            print(example.name)
            _write_fixtures(example.stem)
            proc = subprocess.Popen([sys.executable, str(RUNNER), str(example), str(PORT)],
                                    cwd=str(ROOT), stdout=subprocess.DEVNULL)
            try:
                if not _wait_port(PORT):
                    print(f'  {example.stem}: did not start')
                    failed.append(example.stem)
                    continue
                if not _capture(page, example):
                    failed.append(example.stem)
            finally:
                proc.terminate()
                try:
                    proc.wait(5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                # The port has to be free again before the next example claims it.
                for _ in range(50):
                    try:
                        with socket.create_connection(('127.0.0.1', PORT), 0.2):
                            time.sleep(0.1)
                    except OSError:
                        break
        browser.close()

    if failed:
        print(f'\nfailed: {", ".join(failed)}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
