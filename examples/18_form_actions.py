"""
# Actions — buttons that are not fields

A form sometimes needs a button that is **not** a field: *Test connection* next to the host,
*Generate* next to the password, *Test all* in the title row. It has no value, no validation and
no place in the model — so it is layout, not a field.

Two parts, because a callback cannot live in a layout string:

- `actions={'test': FormAction(...)}` — the table of what the buttons *do*
- `'@test'` in the layout — where the button *sits*, next to the fields it belongs to

```python
ModelForm.from_item(cfg,
    layout=[['# Server', ['host', 'port', '@test']]],
    actions={'test': FormAction('Test', icon='bolt', on_click=test_connection)})
```

The callback receives the usual event arguments — `e.form` is the form, so `e.form.item` (the
last fully valid state) and `e.form.draft` (what the widgets currently hold) are one step away.
Sync or async, like every other niceview handler.

`requires_valid=True` greys the button out while the form has validation errors: the one bit of
state worth taking over, since niceview knows `has_validation_errors` anyway. Everything else the
application does on the returned button — `form.w('@test')`, or `form.action_buttons['test']`.

Every wrapper's title row takes the same `FormAction` under `chrome_actions=`, left of niceview's
own buttons so those keep the right edge they have everywhere else. The callback gets what that
place is about:

| Title row of | The event names |
|---|---|
| `ModelForm`, `EditFormWrapper` | `e.form`, as above |
| `EditGridWrapper` | `e.row_key`, `e.item` — the selected row, both `None` when nothing is selected |
| `DrillDownWrapper`'s `detail_actions` | `e.key`, `e.item` — the item on screen; shown in the detail view only, left of Delete |
| `DrillDownWrapper`'s `list_actions` | no `key`/`item` — the list view is about no single item; shown in the list view only, left of Add |

`DrillDownWrapper` has two views and therefore two action tables — `chrome_actions=` is still
accepted as an alias of `detail_actions=`.

`requires_valid` goes only where a form can answer it: not on a grid, not on `list_actions`, and
not on a drill-down whose detail view you render yourself.

An action carries no *role* — those are niceview's closed vocabulary (add, delete, save, …) — so
it styles itself with `props`, on top of the place and shape of the surrounding chrome.
"""

import asyncio
import secrets
from pathlib import Path

import pydantic
from nicegui import ui

from niceview import DrillDownWrapper, EditFormWrapper, EditGridWrapper, FormAction, ModelForm

JSON_PATH = Path(__file__).parent.parent / 'example_connection.json'


class Connection(pydantic.BaseModel):
    host: str = pydantic.Field(default='db.example.com', title='Host')
    port: int = pydantic.Field(default=5432, title='Port', ge=1, le=65535)
    user: str = pydantic.Field(default='alice', title='User')
    password: str = pydantic.Field(default='changeme42', title='Password', min_length=8)

    class Meta:
        profiles = {
            'setup': [
                ['# Server', ['host', 'port:sm:w-1/4', '@test']],
                ['# Credentials', 'user', ['password', '@generate']],
            ],
        }


async def test_connection(e) -> None:
    """A slow action: the draft is what the user sees, even if it does not validate yet."""
    draft = e.form.draft
    ui.notify(f'Connecting to {draft.host}:{draft.port} …', type='info')
    await asyncio.sleep(1)
    ui.notify(f'{draft.host} answered', type='positive')


def generate_password(e) -> None:
    """Write into a widget, not into the item: the form validates and commits it as usual."""
    e.form.w('password').set_value(secrets.token_urlsafe(12))


def ping_selected(e) -> None:
    """A grid has a selection, not an item — and an empty one is a case of its own."""
    if e.item is None:
        ui.notify('Select a row first', type='warning')
        return
    ui.notify(f'Pinging {e.item.host} …', type='info')


def ping_open(e) -> None:
    """A detail_actions action lives in the detail view, so there is always an item."""
    ui.notify(f'Pinging {e.item.host} (key {e.key}) …', type='info')


def ping_all(e) -> None:
    """A list_actions action lives in the list view — no item, just the wrapper itself."""
    count = sum(1 for _ in e.wrapper.adapter.items())
    ui.notify(f'Pinging all {count} replicas …', type='info')


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    # One list per wrapper below, so that a click in the grid cannot surprise the drill-down.
    servers = [Connection(host='db1.example.com'), Connection(host='db2.example.com', port=5433)]
    replicas = [Connection(host='replica-a', user='bob'), Connection(host='replica-b', user='carol')]

    with ui.row().classes('w-full items-start gap-4'):
        with ui.card().classes('flex-1'):
            ui.label('In the layout').classes('text-h6')
            ui.label("'@test' and '@generate' sit between the fields they belong to.") \
                .classes('text-caption')
            ModelForm.from_item(
                Connection(), profile='setup',
                base_props='outlined dense', default_classes='w-full',
                actions={
                    'test': FormAction('Test', icon='bolt', on_click=test_connection,
                                       tooltip='Try to reach the server'),
                    'generate': FormAction('', icon='casino', on_click=generate_password,
                                           tooltip='Generate a password'),
                },
            ).render()

        with ui.card().classes('flex-1'):
            ui.label('In the title row').classes('text-h6')
            ui.label('chrome_actions= puts the same FormAction next to Refresh and Save. '
                     'Empty the password to see requires_valid grey the button out.') \
                .classes('text-caption')
            EditFormWrapper.from_json(
                Connection, JSON_PATH, title='Connection',
                base_props='outlined dense', default_classes='w-full',
                chrome_actions={
                    'check': FormAction('Test', icon='bolt', requires_valid=True,
                                        tooltip='Try to reach the server and log in',
                                        on_click=lambda e: ui.notify(
                                            f'Checking {e.form.item.host} …', type='info')),
                },
            ).render()

    with ui.row().classes('w-full items-start gap-4'):
        with ui.card().classes('flex-1'):
            ui.label('In a grid title row').classes('text-h6')
            ui.label('The same FormAction, answered with the selected row — Ping without a '
                     'selection says so, exactly as Edit and Delete do.').classes('text-caption')
            EditGridWrapper.from_list(
                Connection, servers, title='Servers',
                chrome_actions={'ping': FormAction('Ping', icon='wifi_tethering', on_click=ping_selected,
                                                   tooltip='Ping the selected server')},
            ).render()

        with ui.card().classes('flex-1'):
            ui.label('In a drill-down title row').classes('text-h6')
            ui.label('"Ping all" sits left of Add in the list view; open a server to see it '
                     'swap for "Ping" left of Delete in the detail view — one table per view.') \
                .classes('text-caption')
            DrillDownWrapper.from_list(
                Connection, replicas, title='Replicas', item_title_field='host',
                list_actions={'ping_all': FormAction('Ping all', icon='wifi_tethering', on_click=ping_all,
                                                      tooltip='Ping every replica')},
                detail_actions={'ping': FormAction('Ping', icon='wifi_tethering', on_click=ping_open,
                                                   tooltip='Ping the server on screen')},
            ).render()


ui.run(title='18 — Actions')
