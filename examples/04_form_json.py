"""
# ModelForm — JSON Persistence

Two rows, each pairing a form variant with a live JSON file viewer:

- **Row 1 — Autosave**: writes to disk after every validated change (often after leaving a field); no button needed.
- **Row 2 — Save / Refresh buttons**: explicit control; *Save* persists, *Refresh* reloads.

Each row uses its own JSON file so you can observe both modes independently.
Each JSON viewer re-reads its file from disk once per second.
"""
import json
from pathlib import Path

import pydantic
from nicegui import ui
from niceview import EditFormWrapper


class AppConfig(pydantic.BaseModel):
    app_name: str = pydantic.Field(default='My App', max_length=40, title='App Name')
    debug: bool = pydantic.Field(default=False, title='Debug Mode')
    max_items: int = pydantic.Field(default=100, ge=1, le=10000, title='Max Items')
    description: str = pydantic.Field(default='', max_length=200, title='Description')


AUTOSAVE_PATH = Path('./example_config_autosave.json')
BUTTONS_PATH  = Path('./example_config_buttons.json')


def make_json_viewer(path: Path) -> None:
    """Render a JSON file viewer card for the given path."""
    content = ui.code('', language='json').classes('w-full')

    def reload():
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
            content.set_content(json.dumps(raw, indent=2))
        except FileNotFoundError:
            content.set_content('(file not yet created)')

    reload()
    ui.timer(1, reload)  # re-read the file every second
    ui.label('Auto-refreshes every second').classes('text-small')


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.row().classes('w-full items-start gap-4'):
        with ui.card().classes('flex-1'):
            EditFormWrapper.from_json(AppConfig, AUTOSAVE_PATH,
                                      title='Edit JSON (autosaves on change)',
                                      autosave=True,
                                      ).render()

        with ui.card().classes('flex-1'):
            ui.label(f'JSON — {AUTOSAVE_PATH.name}').classes('text-h6')
            make_json_viewer(AUTOSAVE_PATH)

    with ui.row().classes('w-full items-start gap-4 mt-4'):
        with ui.card().classes('flex-1'):
            EditFormWrapper.from_json(
                AppConfig, BUTTONS_PATH,
                title='Edit JSON (uses Save / Refresh buttons)',
            ).render()

        with ui.card().classes('flex-1'):
            ui.label(f'JSON — {BUTTONS_PATH.name}').classes('text-h6')
            make_json_viewer(BUTTONS_PATH)


ui.run(title='04 — Form JSON')
