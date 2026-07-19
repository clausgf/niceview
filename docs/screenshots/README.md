Screenshot generation
======================

Reproducible README screenshots, rendered headlessly with Playwright + Chromium.

- `apps.py` — a small NiceGUI app (routes `/hero`, `/grid`, `/drilldown`) built from
  one deliberately varied `Deployment` model, styled `outlined dense` for an app-like look.
- `capture.py` — starts `apps.py`, drives it with Playwright, and writes the images into
  `../img/`.

```bash
uv sync --group screenshots
uv run playwright install chromium   # once, to fetch the browser binary
uv run python docs/screenshots/capture.py
```

This tooling lives in the optional `screenshots` dependency group and is not needed to
use, develop, or test the library.
