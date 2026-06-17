"""
# ModelForm — JSON Persistence

Two rows, each pairing a form variant with a live JSON file viewer:

- **Row 1 — Autosave**: writes to disk after every validated change; no button needed.
- **Row 2 — Save / Refresh buttons**: explicit control; *Save* persists, *Refresh* reloads.

Each row uses its own JSON file so you can observe both modes independently.
The *Reload* button in each viewer re-reads the file from disk.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui
from niceview.modelform import ModelForm


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
    ui.button('Reload', icon='refresh', on_click=reload).props('flat dense')


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.row().classes('w-full items-start gap-4'):
        with ui.card().classes('flex-1'):
            ui.label('Autosave').classes('text-h6')
            ModelForm.from_json(AppConfig, AUTOSAVE_PATH, autosave=True, classes='w-full').render()

        with ui.card().classes('flex-1'):
            ui.label(f'JSON — {AUTOSAVE_PATH.name}').classes('text-h6')
            make_json_viewer(AUTOSAVE_PATH)

    with ui.row().classes('w-full items-start gap-4 mt-4'):
        with ui.card().classes('flex-1'):
            ui.label('Save / Refresh buttons').classes('text-h6')
            ModelForm.from_json(
                AppConfig, BUTTONS_PATH,
                save_button='Save', refresh_button='Refresh',
                classes='w-full',
            ).render()

        with ui.card().classes('flex-1'):
            ui.label(f'JSON — {BUTTONS_PATH.name}').classes('text-h6')
            make_json_viewer(BUTTONS_PATH)


ui.run(title='04 — Form JSON')
