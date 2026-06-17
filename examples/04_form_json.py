"""
# ModelForm — JSON Persistence

Two forms backed by the same JSON file, showing the two persistence modes:

- **Autosave** — writes to disk after every validated change (no button needed)
- **Save / Refresh buttons** — explicit control; Refresh reloads from disk

A third panel reads the raw JSON file from disk so you can watch the file
content change as you edit. Click *Reload* in that panel to refresh it.

The JSON file is created with default values on first run.
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


CONFIG_PATH = Path('./example_config.json')


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.row().classes('w-full items-start gap-4'):
        with ui.card().classes('flex-1'):
            ui.label('Autosave').classes('text-h6')
            ModelForm.from_json(AppConfig, CONFIG_PATH, autosave=True, classes='w-full').render()

        with ui.card().classes('flex-1'):
            ui.label('Save / Refresh buttons').classes('text-h6')
            ModelForm.from_json(
                AppConfig, CONFIG_PATH,
                save_button='Save', refresh_button='Refresh',
                classes='w-full',
            ).render()

        with ui.card().classes('flex-1'):
            ui.label('Raw JSON on disk').classes('text-h6')
            content = ui.code('', language='json').classes('w-full')

            def reload_json():
                try:
                    raw = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
                    content.set_content(json.dumps(raw, indent=2))
                except FileNotFoundError:
                    content.set_content('(file not found)')

            reload_json()
            ui.button('Reload', icon='refresh', on_click=reload_json).props('flat dense')


ui.run(title='04 — Form JSON')
