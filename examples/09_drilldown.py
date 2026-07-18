"""
# DrillDownWrapper / ModelList

Embeddable list <-> detail navigation: a contact list that opens a detail form per item.

`DrillDownWrapper` renders a title row (Add in list view; Back + item title + Delete in
detail view) plus a body that swaps between the list and a per-item form, with a slide
animation on every swap. It owns no NiceGUI page/route of its own — render() draws into
whatever context it's called in, here a single `@ui.page('/')`.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui
from niceview import DrillDownWrapper


class Contact(pydantic.BaseModel):
    name: str = pydantic.Field(default='', min_length=1, max_length=50, title='Name')
    email: str = pydantic.Field(default='', title='Email')
    phone: str = pydantic.Field(default='', title='Phone')
    notes: str = pydantic.Field(default='', title='Notes')


contacts = [
    Contact(name='Alice Müller', email='alice@example.com', phone='+49 170 1234567', notes='Project lead'),
    Contact(name='Bob Schmidt', email='bob@example.com', phone='+49 171 2345678'),
    Contact(name='Carol Meier', email='carol@example.com', phone='+49 172 3456789', notes='Customer'),
]


@ui.page('/')
def page():
    with ui.card().classes('w-full max-w-2xl mx-auto'):
        DrillDownWrapper.from_list(
            Contact, contacts,
            list_title='Contacts',
            item_title_field='name',
            item_subtitle_fields=['email', 'phone'],
        ).render()


ui.run(title='09 — Drill-Down Navigation')
