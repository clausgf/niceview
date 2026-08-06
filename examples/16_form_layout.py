"""
# ModelForm — Layout

By default a form stacks its fields. A **layout** arranges them, written as a nested list of
field names — in `Meta.profiles` when it belongs to the model, or as `layout=` for one form.

| Notation | Meaning |
|---|---|
| `'city'` | the field |
| `'zip_code:sm:w-1/3'` | the field, with CSS classes — only the **first** colon separates, so Tailwind prefixes (`sm:`, `hover:`) stay intact |
| `['zip_code', 'city']` | a nested list opens a container: rows and columns alternate with each level |
| `'# Address'` | as the **first** element: the group becomes a card with that title |
| `':gap-8 items-end'` | as the **first** element: replaces the container's default classes |

Two rules worth knowing, both about not fighting Tailwind:

- Fields in a row share the width evenly (`flex-1`). A field that brings its own classes gets
  those *instead* — `flex-1` sets `flex-basis: 0` and would silently win over any width.
- Container classes **replace** the defaults instead of adding to them: `gap-4 gap-8` is decided
  by stylesheet order, not by the order in the class list.

The layout also defines *which* fields are rendered, exactly like a profile — see the third tab,
where `notes` is missing on purpose. What the notation cannot express, `form.render_field()`
still can: it places one field wherever you call it.

Uniform styling is a separate knob: `field_props` and `field_classes` apply to **every** widget
of the form, whatever its type — `ui.select` and `ui.input_chips` included, which
`ui.input.default_props()` would miss. They come first in the cascade
(`field_classes` → the field's own `niceview.Field(classes=...)` → the layout's classes), so
`field_classes='w-full'` sets the baseline and a layout hint refines it.
"""

import pprint
from typing import Annotated, Literal

import pydantic
from nicegui import ui

import niceview
from niceview import ModelForm


class Contact(pydantic.BaseModel):
    first_name: str = pydantic.Field(default='Alice', title='First name')
    last_name: str = pydantic.Field(default='Turing', title='Last name')
    email: str = pydantic.Field(default='alice@example.com', title='E-mail',
                                description='We only use it for the order confirmation')
    phone: str = pydantic.Field(default='+49 30 123456', title='Phone')
    street: str = pydantic.Field(default='Main Street 1', title='Street')
    zip_code: str = pydantic.Field(default='12345', title='ZIP')
    city: str = pydantic.Field(default='Berlin', title='City')
    country: Literal['DE', 'AT', 'CH'] = pydantic.Field(default='DE', title='Country')
    notes: Annotated[str, niceview.Field(widget_type='ui.textarea')] = pydantic.Field(
        default='', title='Notes')

    class Meta:
        # A profile may be nested: it is a field selection *and* an arrangement. Grids and
        # lists read the same entry and simply ignore the nesting.
        profiles = {
            'card': [
                ['# Name', ['first_name', 'last_name']],
                ['# Address', 'street', ['zip_code:sm:w-1/3', 'city'], 'country:sm:w-1/2'],
            ],
        }


ROWS = [
    ['first_name', 'last_name'],
    ['email', 'phone'],
    'street',
    [':gap-8', 'zip_code:sm:w-1/3', 'city'],
    'country:sm:w-1/2',
    'notes',
]


# Applied to every widget of the form, whatever its type. 'w-full' makes a field fill its
# container; inside a row 'flex-1' takes over, and a layout hint like 'sm:w-1/3' wins above the
# breakpoint — which leaves 'w-full' as the sensible fallback on a narrow screen.
FORM_STYLE = {'field_props': 'outlined dense', 'field_classes': 'w-full'}


def show(title: str, description: str, source: object, render) -> None:
    """One tab: the layout literal on the left, the form it produces on the right."""
    ui.label(title).classes('text-h6')
    ui.label(description).classes('text-caption')
    with ui.row().classes('w-full items-start gap-4 mt-2'):
        with ui.card().classes('flex-1'):
            ui.code(pprint.pformat(source, width=64, sort_dicts=False), language='python').classes('w-full')
        with ui.card().classes('flex-1'):
            render()


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.tabs().classes('w-full') as tabs:
        tab_stacked = ui.tab('Stacked (default)')
        tab_rows = ui.tab('Rows')
        tab_sections = ui.tab('Sections (profile)')

    with ui.tab_panels(tabs, value=tab_stacked).classes('w-full'):
        with ui.tab_panel(tab_stacked):
            show('No layout', 'Every field on its own line, in model order.',
                 'ModelForm.from_item(contact)',
                 lambda: ModelForm.from_item(Contact(), **FORM_STYLE).render())

        with ui.tab_panel(tab_rows):
            show('layout=[...]', 'Nested lists open rows; the ZIP keeps a third of the line.',
                 ROWS,
                 lambda: ModelForm.from_item(Contact(), layout=ROWS, **FORM_STYLE).render())

        with ui.tab_panel(tab_sections):
            show("profile='card'", 'Titled groups render as flat bordered cards. Note that `notes` is not part of this profile.',
                 Contact.Meta.profiles['card'],
                 lambda: ModelForm.from_item(Contact(), profile='card', **FORM_STYLE).render())


ui.run(title='16 — Form Layout')
