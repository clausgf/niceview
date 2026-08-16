"""
# ModelForm — Actions

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

The title row takes the same `FormAction` under `chrome_actions=`, left of Refresh and Save so
that niceview's own buttons keep the right edge they have everywhere else. An action carries no
*role* — those are niceview's closed vocabulary (add, delete, save, …) — so it styles itself with
`props`, on top of the place and shape of the surrounding chrome.
"""

import asyncio
import secrets
from pathlib import Path

import pydantic
from nicegui import ui

from niceview import EditFormWrapper, FormAction, ModelForm

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


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

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


ui.run(title='18 — Form Actions')
