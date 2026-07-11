"""
# Card-Based List Editing

`ModelGrid`/`EditGridWrapper` render a list as a table with Add/Edit/Delete dialogs — great for
dense data, less so on mobile or when each item needs its own layout. This example builds a
mobile-friendly alternative from scratch: one card per item, each with its own autosaving
`ModelForm` and a custom `render_field()` layout, backed by a `JsonListAdapter`.

There is no dedicated wrapper class for this — the card layout is inherently
application-specific, so it's composed directly from `ModelForm.from_adapter()`,
`CollectionAdapter.create()`/`delete()`, and NiceGUI's `@ui.refreshable`.

Each card's form uses `autosave=True`, so edits persist to the JSON file field-by-field
(after validation, on blur/change) — no shared save button, no row selection. The raw JSON
file is shown live below the cards.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
import json
from pathlib import Path
from typing import Literal
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui

from niceview.dataadapter import JsonListAdapter
from niceview.form import ModelForm


class Webhook(pydantic.BaseModel):
    name: str = pydantic.Field(default='', min_length=1, max_length=40, pattern=r'^[a-zA-Z0-9_-]*$', title='Name')
    method: Literal['GET', 'POST', 'PUT', 'DELETE'] = pydantic.Field(default='POST', title='Method')
    url: str = pydantic.Field(default='https://', max_length=200, pattern=r'^https?://.*', title='URL')


WEBHOOKS_PATH = Path('./example_webhooks.json')
adapter = JsonListAdapter(Webhook, WEBHOOKS_PATH)


@ui.refreshable
def render_cards() -> None:
    for key, item in adapter.items():
        form = ModelForm.from_adapter(Webhook, adapter, key, autosave=True)
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center'):
                form.render_field('name').classes('grow').props('outlined dense hide-bottom-space')
                ui.button(icon='delete').props('color=negative dense flat').on_click(
                    lambda _, it=item: delete_row(it)
                )
            with ui.row().classes('w-full'):
                form.render_field('method').classes('w-1/4').props('outlined dense hide-bottom-space')
                form.render_field('url').classes('grow').props('outlined dense hide-bottom-space')
            form.render_nonfield_errors()


def add_row() -> None:
    adapter.create(Webhook(name=f'hook_{len(list(adapter)) + 1}'))
    render_cards.refresh()


def delete_row(item: Webhook) -> None:
    adapter.delete(adapter.key_from_item(item))
    render_cards.refresh()


def render_json_viewer() -> None:
    content = ui.code('', language='json').classes('w-full')

    def reload():
        try:
            content.set_content(json.dumps(json.loads(WEBHOOKS_PATH.read_text(encoding='utf-8')), indent=2))
        except FileNotFoundError:
            content.set_content('(file not yet created)')

    reload()
    ui.timer(1, reload)
    ui.label('Auto-refreshes every second').classes('text-caption')


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.row().classes('w-full items-start gap-4'):
        with ui.column().classes('flex-1'):
            render_cards()
            ui.button('Add Webhook', icon='add', on_click=add_row).props('color=primary')

        with ui.card().classes('flex-1'):
            ui.label(f'JSON — {WEBHOOKS_PATH.name}').classes('text-h6')
            render_json_viewer()


ui.run(title='12 — Card List')
