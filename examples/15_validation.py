"""
# Validation — three layers, and what gets written when

Every change runs through the same three layers, in this order:

| Layer | Rule | Try it |
|---|---|---|
| 1a | `required` — rejects an empty value (a field without a default is required automatically) | clear **Name** |
| 1b | `niceview.Field(validation=...)` — a callable or a `{message: predicate}` dict | type a digit into **Name**, or remove the `@` from **E-mail** |
| 2 | value conversion to the field's Python type | clear **Arrival** and type something that is not a date |
| 3 | the whole item against the Pydantic model (`ModelForm` only) | type 30 into **Nights**, or start a long stay on a weekend |

Layers 1a/1b are the widget's own and work without a model — `render_field()` runs exactly
these (see `14_render_field.py`). Layer 3 is what `ModelForm` adds: it validates the *whole*
item after every change, so a `@model_validator` error shows up under the form, where no single
field could show it.

**Nothing is written while any layer complains.** The panel on the right makes that visible:

- `form.item` — the last state that validated as a whole; this is what *Save* writes
- `form.draft` — what the widgets currently hold, invalid values included

Edit **Nights** to 10 while **Arrival** is a Saturday: the cross-field rule fails, `item` stops
following, `draft` keeps up, and *Save* refuses. Fix either field and both pending edits are
committed together — one change event per field that really changed.

`Confirmed at` is `frozen=True` in the model, so the widget is disabled: pydantic would raise
on every write to it.
"""

import datetime
from pathlib import Path

import pydantic
from nicegui import ui
from typing import Annotated

import niceview
from niceview import EditFormWrapper

PATH = Path('./example_booking.json')


def _letters_only(value: str | None) -> str | None:
    """A plain NiceGUI validation callback: returns a message, or None when the value is fine."""
    if value and not value.replace(' ', '').isalpha():
        return 'letters and spaces only'
    return None


class Booking(pydantic.BaseModel):
    # required: the label gets a ' *' and an empty value is rejected. A field without a
    # default is required automatically; here it is stated explicitly so that the JSON file
    # can still be created from the model's defaults — UI-level required is not pydantic's.
    name: Annotated[
        str,
        pydantic.Field(title='Name', max_length=20, description='As printed on the passport'),
        niceview.Field(required=True, validation=_letters_only),
    ] = 'Alice'
    email: Annotated[
        str,
        pydantic.Field(title='E-mail'),
        niceview.Field(validation={'must contain @': lambda v: '@' in (v or '')}),
    ] = 'alice@example.com'
    guests: int = pydantic.Field(default=2, ge=1, le=8, title='Guests')
    arrival: datetime.date = pydantic.Field(default_factory=datetime.date.today, title='Arrival')
    nights: int = pydantic.Field(default=3, ge=1, le=28, title='Nights')
    confirmed_at: str = pydantic.Field(default='not confirmed', title='Confirmed at', frozen=True)

    @pydantic.model_validator(mode='after')
    def _long_stays_start_on_a_weekday(self):
        # A cross-field rule: it belongs to no single widget, so it is shown under the form.
        if self.nights > 7 and self.arrival.weekday() >= 5:
            raise ValueError('a stay longer than a week cannot start on a weekend')
        return self


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.row().classes('w-full items-start gap-4'):
        with ui.card().classes('flex-1'):
            wrapper = EditFormWrapper.from_json(Booking, PATH, title='Booking').render()
            form = wrapper.form

        with ui.card().classes('flex-1'):
            ui.label('Form state').classes('text-h6')
            state = ui.label().classes('text-weight-bold')
            ui.label('form.item — last fully valid state, this is what Save writes').classes('text-caption')
            item_view = ui.code('', language='json').classes('w-full')
            ui.label('form.draft — what the widgets hold right now').classes('text-caption')
            draft_view = ui.code('', language='json').classes('w-full')
            errors_view = ui.label().classes('text-negative')

            def update() -> None:
                state.set_text('invalid — Save refuses' if form.has_validation_errors else 'valid')
                state.classes(replace='text-weight-bold ' + ('text-negative' if form.has_validation_errors else 'text-positive'))
                item_view.set_content(form.item.model_dump_json(indent=2))
                draft_view.set_content(form.draft.model_dump_json(indent=2))
                errors = [f'{k}: {v}' for k, v in form.validation_errors.items()] + form.nonfield_validation_errors
                errors_view.set_text(' | '.join(errors))

            update()
            ui.timer(0.3, update)

    log = ui.log(max_lines=8).classes('w-full h-32 mt-4')
    log.push('Change events (one per field, on commit):')
    form.on_change(lambda e: log.push(f'{e.field_name}: {e.previous_value!r} → {e.value!r}'))


ui.run(title='15 — Validation')
