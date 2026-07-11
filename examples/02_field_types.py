"""
# ModelForm — Field Types

One form showing all field types supported by NiceView:

| Python type | Widget |
|---|---|
| `str` | `ui.input` or `ui.textarea` (via `widget_type` override) |
| `str` with `password=True` | `ui.input` (password mode with toggle) |
| `str` with `autocomplete=[...]` | `ui.input` (with autocomplete dropdown) |
| `int`, `float` | `ui.number` |
| `int`/`float` with `prefix`/`suffix` | `ui.number` (with unit decoration) |
| `bool` | `ui.switch` or `ui.checkbox` |
| `datetime.date` | HTML date input |
| `datetime.time` | HTML time input |
| `datetime.datetime` | HTML datetime-local input |
| `datetime.timedelta` | `ui.input` (ISO 8601 duration) |
| `Literal[...]` | `ui.select`, `ui.radio`, or `ui.toggle` (via `widget_type` override) |
| `Literal[...]` with `with_input=True` | `ui.select` (searchable) |
| `list[str]` with `select_options` + `multiple=True` | `ui.select` (multi-select) |
| `list[Literal[...]]` | `ui.select` (multi-select; options from the `Literal`, no `select_options` needed) |
| `list[Literal[...]]` with `props='use-chips'` | `ui.select` (multi-select, selections shown as removable chips) |
| `list[Literal[...]]` with `widget_type='checkbox_group'` | Row/column of `ui.checkbox` (alternative to the multi-select) |
| `str` (color) | `ui.color_input` (via `widget_type` override) |
| `list[str]` | `ui.input_chips` |
| `list[Annotated[str, Field(pattern=...)]]` | `ui.input_chips` (item constraints enforced by validation, not the widget) |
| `list[int]`, `list[float]`, `list[bool]` | `ui.input` (comma-separated) |
| `int` with `ge`/`le` + `widget_type='ui.slider'` | `ui.slider` |
| `int` with `le` + `widget_type='ui.rating'` | `ui.rating` |
| `list[BaseModel]` | Inline `EditGridWrapper` |

This example also demonstrates how to customize the widgets, layout and style via `niceview.Field` metadata, ui.grid() and `ElementFilter`.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime
from typing import Annotated, Literal
import pydantic
from nicegui import ElementFilter, ui

import niceview
from niceview.form import ModelForm


class Tag(pydantic.BaseModel):
    label: str = pydantic.Field(default='', title='Label')

    def __str__(self):
        return self.label


class AllTypes(pydantic.BaseModel):
    text: str = pydantic.Field(default='hello', title='String')
    text_area: Annotated[str, niceview.Field(widget_type='ui.textarea', label='String in Textarea')] = 'hello\nworld'
    password: Annotated[str, pydantic.Field(title='Password'), niceview.Field(password=True, password_toggle_button=True)] = 'hunter2'
    city: Annotated[str, pydantic.Field(title='City (autocomplete)'), niceview.Field(autocomplete=['Berlin', 'Munich', 'Hamburg', 'Cologne', 'Frankfurt', 'Stuttgart'])] = 'Berlin'
    number_int: int = pydantic.Field(default=42, ge=0, le=1000, title='Integer (0-1000)')
    number_float: float = pydantic.Field(default=3.14, title='Float')
    speed: Annotated[float, pydantic.Field(title='Speed'), niceview.Field(suffix=' km/h', precision=1)] = 120.0
    flag_switch: bool = pydantic.Field(default=True, title='Bool')
    flag_checkbox: Annotated[bool, pydantic.Field(title='Bool in Checkbox'), niceview.Field(widget_type='ui.checkbox')] = False
    date: datetime.date = pydantic.Field(default_factory=datetime.date.today, title='Date')
    time: datetime.time = pydantic.Field(default_factory=lambda: datetime.time(9, 0), title='Time')
    dt: datetime.datetime = pydantic.Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0),
        title='Datetime',
    )
    duration: datetime.timedelta = pydantic.Field(
        default_factory=lambda: datetime.timedelta(hours=1, minutes=30),
        title='Timedelta',
    )
    choice: Literal['red', 'green', 'blue'] = 'green' # label and widget are auto-detected from the Literal type
    choice_search: Annotated[Literal['apple', 'banana', 'cherry', 'date', 'elderberry'], niceview.Field(widget_type='ui.select', with_input=True, label='Fruit (searchable select)')] = 'apple'
    choice_multi: Annotated[list[str], niceview.Field(widget_type='ui.select', select_options=['red', 'green', 'blue'], multiple=True, clearable=True)] = pydantic.Field(default_factory=lambda: ['red', 'blue'], title='Colors (multi-select)')
    perms_multiselect: list[Literal['read', 'write', 'admin']] = pydantic.Field(default_factory=lambda: ['read'], title='Permissions (list[Literal], auto multi-select)')  # type: ignore[arg-type]
    perms_chips: Annotated[list[Literal['read', 'write', 'admin']], niceview.Field(props='use-chips', label='Permissions (multi-select with use-chips)')] = pydantic.Field(default_factory=lambda: ['read'])  # type: ignore[arg-type]
    perms_checkboxes: Annotated[list[Literal['read', 'write', 'admin']], niceview.Field(widget_type='checkbox_group', props='inline', label='Permissions (checkbox_group)')] = pydantic.Field(default_factory=lambda: ['read'])  # type: ignore[arg-type]
    choice_radio: Annotated[Literal['red', 'green', 'blue'], niceview.Field(widget_type='ui.radio', props='inline')] = 'green'
    choice_toggle: Annotated[Literal['red', 'green', 'blue'], niceview.Field(widget_type='ui.toggle')] = 'green'
    color: Annotated[str, niceview.Field(widget_type='ui.color_input', label='Color', color_preview=True)] = '#4a90e2'
    volume: Annotated[int, pydantic.Field(ge=0, le=100, title='Volume'), niceview.Field(widget_type='ui.slider', step=1)] = 50
    priority: Annotated[int, pydantic.Field(ge=1, le=5, title='Priority'), niceview.Field(widget_type='ui.rating')] = 3
    chips: list[str] = pydantic.Field(default_factory=lambda: ['foo', 'bar'], title='Chips (list[str])')
    chips_constrained: list[Annotated[str, pydantic.Field(pattern=r'^[a-z]+$', min_length=2, max_length=10)]] = pydantic.Field(
        default_factory=lambda: ['ok', 'go'],
        title='Chips (constrained items: lowercase, 2-10 chars)',
    )
    nums: list[int] = pydantic.Field(default_factory=lambda: [1, 2, 3], title='Numbers (list[int], comma-separated)')
    tags: list[Tag] = pydantic.Field(
        default_factory=lambda: [Tag(label='important')],
        title='Tags (list of BaseModel with __str__ method)',
    )

@ui.page('/')
def page():
    # Styling example: make all inputs outlined and dense
    #app.colors(primary='#800000)
    #ui.input.default_props('outlined dense')

    with ui.tabs().classes('w-full') as tabs:
        tab_home = ui.tab('Documentation')
        tab_all_types = ui.tab('All Types')

    with ui.tab_panels(tabs, value=tab_home).classes('w-full') as panels:

        with ui.tab_panel(tab_home):
            ui.markdown(__doc__ or '')

        with ui.tab_panel(tab_all_types):
            with ui.grid().classes('w-full gap-4 grid-cols-1 lg:grid-cols-2').mark('my-form'):
                ModelForm.from_item(AllTypes()).render()

    # Styling example: make all my-form elements outlined and dense
    ElementFilter().within(marker='my-form').props('outlined dense')

ui.run(title='02 — Field Types')
