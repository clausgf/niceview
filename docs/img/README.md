Documentation images
=====================

These images are embedded in the top-level `README.md`:

- `hero.png` — a styled `ModelForm` showing the range of widget types
- `grid.png` — an `EditGridWrapper` with its CRUD buttons
- `drilldown.gif` — the `DrillDownWrapper` list ↔ detail navigation

They are generated (not hand-captured) by [`../screenshots/capture.py`](../screenshots/capture.py),
so they stay reproducible. To regenerate:

```bash
uv sync --group screenshots
uv run playwright install chromium   # once
uv run python docs/screenshots/capture.py
```

Keep embedded images small (these are all well under 150 KB); the capture script
already downscales and quantizes the GIF.
