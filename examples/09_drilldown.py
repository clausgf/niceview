"""
# DrillDownWrapper / ModelList

Responsive drill-down navigation: a contact list that opens a detail form per item.

- **/contacts** — list page: all contacts as a tappable list, Add button in the header
- **/contacts/{key}** — detail page: full form with Save, Refresh, Back, and Delete

Both pages are registered by `DrillDownWrapper.register('/contacts')` before `ui.run()`.
The root `/` redirects to `/contacts`.

**Responsive split-panel layout:**
- On mobile (< 1024 px): list page and detail page navigate separately (drill-down style)
- On desktop (≥ 1024 px): list appears on the left, detail form on the right (side by side)

No API changes — the responsive behaviour is built in via Quasar breakpoint CSS classes.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui
from niceview.modellist import DrillDownWrapper


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


DrillDownWrapper.from_list(
    Contact, contacts,
    title='Contacts',
    title_field='name',
    subtitle_fields=['email', 'phone'],
).register('/contacts')


@ui.page('/')
def index():
    ui.navigate.to('/contacts')


ui.run(title='09 — Drill-Down Navigation')
