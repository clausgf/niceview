"""
# ModelForm — Field Types

One form showing all field types supported by NiceView:

| Python type | Widget |
|---|---|
| `str` | `ui.input` or `ui.textarea` (via `widget_type` override) |
| `int`, `float` | `ui.number` |
| `bool` | `ui.switch` or `ui.checkbox` |
| `datetime.date` | HTML date input |
| `datetime.time` | HTML time input |
| `datetime.datetime` | HTML datetime-local input |
| `datetime.timedelta` | `ui.input` (ISO 8601 duration) |
| `Literal[...]` | `ui.select`, `ui.radio`, or `ui.toggle` (via `widget_type` override) |
| `str` (color) | `ui.color_input` (via `widget_type` override) |
| `list[str]` | `ui.input_chips` |
| `list[int]`, `list[float]`, `list[bool]` | `ui.input` |
| `int` with `ge`/`le` + `widget_type='slider'` | `ui.slider` |
| `int` with `le` + `widget_type='rating'` | `ui.rating` |
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
from niceview.modelform import ModelForm


class Tag(pydantic.BaseModel):
    label: str = pydantic.Field(default='', title='Label')

    def __str__(self):
        return self.label


class AllTypes(pydantic.BaseModel):
    text: str = pydantic.Field(default='hello', title='String')
    text_area: Annotated[str, niceview.Field(widget_type='ui.textarea', label='String in Textarea')] = 'hello\nworld'
    number_int: int = pydantic.Field(default=42, ge=0, le=1000, title='Integer (0-1000)')
    number_float: float = pydantic.Field(default=3.14, title='Float')
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
    choice_radio: Annotated[Literal['red', 'green', 'blue'], niceview.Field(widget_type='ui.radio', props='inline')] = 'green'
    choice_toggle: Annotated[Literal['red', 'green', 'blue'], niceview.Field(widget_type='ui.toggle')] = 'green'
    color: Annotated[str, niceview.Field(widget_type='ui.color_input', label='Color', color_preview=True)] = '#4a90e2'
    volume: Annotated[int, pydantic.Field(default=50, ge=0, le=100, title='Volume'), niceview.Field(widget_type='slider', step=1)]
    priority: Annotated[int, pydantic.Field(default=3, ge=1, le=5, title='Priority'), niceview.Field(widget_type='rating')]
    chips: list[str] = pydantic.Field(default_factory=lambda: ['foo', 'bar'], title='Chips (list[str])')
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
