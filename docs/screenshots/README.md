Screenshot generation
======================

Reproducible README screenshots, rendered headlessly with Playwright + Chromium.

- `apps.py` — a small NiceGUI app (routes `/hero`, `/grid`, `/drilldown`) built from
  one deliberately varied `Deployment` model, styled `outlined dense` for an app-like look.
- `capture.py` — starts `apps.py`, drives it with Playwright, and writes the images into
  `../img/`.
- `capture_examples.py` — the same for the numbered examples: starts each one headlessly
  (via `_serve_example.py`), strips the docstring the page prints for itself, and writes
  `../img/examples/<example>.png`. Those images are what the generated example pages of the
  documentation site show.

```bash
uv sync --group screenshots
uv run playwright install chromium   # once, to fetch the browser binary
uv run python docs/screenshots/capture.py
uv run python docs/screenshots/capture_examples.py         # all examples
uv run python docs/screenshots/capture_examples.py 16 18   # only these
```

Re-run `capture_examples.py` when an example's *appearance* changes; its text needs no run at
all, since the documentation page reads the docstring at build time.

This tooling lives in the optional `screenshots` dependency group and is not needed to
use, develop, or test the library.
