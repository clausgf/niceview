"""
# render_field — a form without a model

`niceview.render_field(field_info, value)` renders **one** widget from **one** `niceview.Field()`,
with no Pydantic model involved; `niceview.field_value(widget, field_info)` reads it back with the
same value conversions `ModelForm` applies. `ModelForm` is built on the same functions, so both
paths produce identical widgets.

Use this when your own code — not a model class — decides what a field is. Here the fields come
from a dict that could just as well have been read from an untrusted JSON file: the field kinds
are mapped to widget types through a table *we* own (`_WIDGETS`), so nothing from the data ever
becomes a Python class.

`required` needs no model: it marks the label and rejects empty values, so a JSON Schema
`required` list is directly usable. `validation=` would add a rule per field, in the same order
a `ModelForm` would run it — see docs/components.md#validation.

A schema's `description` goes into `description=`, not into `hint=`: it is help text without a
fixed place, and `description_as` decides at render time whether it becomes the hint, the
tooltip or nothing — exactly the same knob a `ModelForm` has. `hint=`/`tooltip=` stay for what
*this* code decides to show, and they win over the description.

Note what is *not* here: no change events, no autosave, no model validation, no widget registry.
The caller owns the widgets and reads them when it wants to — see `collect()`.
"""

import datetime
from typing import Any

from nicegui import ui

from niceview import Field, FieldInfo, field_value, render_field

# --- the "schema": eight field kinds we allow, nothing else ----------------

SCHEMA: list[dict[str, Any]] = [
    {'key': 'name', 'kind': 'string', 'label': 'Name', 'required': True, 'value': 'Alice',
     'description': 'Shown in the device list'},
    {'key': 'notes', 'kind': 'textarea', 'label': 'Notes', 'value': 'multi\nline'},
    {'key': 'age', 'kind': 'integer', 'label': 'Age', 'minimum': 0, 'maximum': 120, 'value': 30},
    {'key': 'score', 'kind': 'number', 'label': 'Score', 'value': 4.5},
    {'key': 'active', 'kind': 'boolean', 'label': 'Active', 'value': True},
    {'key': 'color', 'kind': 'enum', 'label': 'Color', 'enum': ['red', 'green', 'blue'], 'value': 'green'},
    {'key': 'start', 'kind': 'date', 'label': 'Start', 'value': '2026-08-05'},
    {'key': 'tags', 'kind': 'string_list', 'label': 'Tags', 'value': ['a', 'b']},
]

# The one place that translates the schema's vocabulary into niceview's.
_WIDGETS: dict[str, str] = {
    'string': 'ui.input',
    'textarea': 'ui.textarea',
    'integer': 'ui.number',
    'number': 'ui.number',
    'boolean': 'ui.switch',
    'enum': 'ui.select',
    'date': 'date',
    'string_list': 'ui.input_chips',
}


def to_field_info(field: dict[str, Any]) -> FieldInfo:
    """Map one schema field to a FieldInfo. Schema strings only ever land in text attributes."""
    kind = field['kind']
    return Field(
        label=field.get('label', field['key']),
        description=field.get('description'),                         # placed by description_as
        required=bool(field.get('required')),                         # -> ' *' marker + non-empty check
        widget_type=_WIDGETS[kind],                                  # type: ignore[typeddict-item]
        field_type=int if kind == 'integer' else str,                # drives field_value()
        options=[str(x) for x in field['enum']] if field.get('enum') else None,
        min=field.get('minimum'),
        max=field.get('maximum'),
        precision=0 if kind == 'integer' else None,
        props='outlined dense',
        classes='w-full',
    )


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    field_infos = {f['key']: to_field_info(f) for f in SCHEMA}
    widgets: dict[str, Any] = {}

    with ui.card().classes('w-96'):
        with ui.column().classes('w-full gap-3'):
            for f in SCHEMA:
                # description_as decides where the schema's `description` goes: 'hint' below the
                # widget, 'tooltip' (the default) on hover, None nowhere.
                widgets[f['key']] = render_field(field_infos[f['key']], f['value'],
                                                 description_as='hint')

    result = ui.log(max_lines=12).classes('w-96 h-48 mt-4')

    def collect() -> None:
        invalid = [key for key, w in widgets.items() if hasattr(w, 'validate') and not w.validate()]
        if invalid:
            result.push(f'invalid: {", ".join(invalid)}')
            return
        values = {key: field_value(w, field_infos[key]) for key, w in widgets.items()}
        result.push(', '.join(f'{k}={v!r}' for k, v in values.items()))
        # date/time/datetime come back as Python objects, ready for json.dumps(default=str)
        assert isinstance(values['start'], datetime.date)

    ui.button('Collect values', on_click=collect).classes('mt-2')


ui.run(title='14 — render_field without a model')
