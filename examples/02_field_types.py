"""
# ModelForm — Field Types

One form showing all field types supported by NiceView:

| Python type | Widget |
|---|---|
| `str` | `ui.input` |
| `int`, `float` | `ui.number` |
| `bool` | `ui.switch` or `ui.checkbox` |
| `datetime.date` | HTML date input |
| `datetime.time` | HTML time input |
| `datetime.datetime` | HTML datetime-local input |
| `datetime.timedelta` | `ui.input` (ISO 8601 duration) |
| `Literal[...]` | `ui.select` |
| `list[str]` | `ui.input_chips` |
| `list[BaseModel]` | Inline `EditGridWrapper` |
"""
import sys
import datetime
from pathlib import Path
from typing import Annotated, Literal
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui

import niceview
from niceview.modelform import ModelForm


class Tag(pydantic.BaseModel):
    label: str = pydantic.Field(default='', title='Label')

    def __str__(self):
        return self.label


class AllTypes(pydantic.BaseModel):
    text: str = pydantic.Field(default='hello', title='Text (str)')
    number_int: int = pydantic.Field(default=42, ge=0, le=1000, title='Integer')
    number_float: float = pydantic.Field(default=3.14, title='Float')
    flag_switch: bool = pydantic.Field(default=True, title='Bool (switch)')
    flag_checkbox: Annotated[bool, niceview.Field(widget_type='ui.checkbox')] = False
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
    choice: Literal['red', 'green', 'blue'] = 'green'
    chips: list[str] = pydantic.Field(default_factory=lambda: ['foo', 'bar'], title='Chips (list[str])')
    tags: list[Tag] = pydantic.Field(
        default_factory=lambda: [Tag(label='important')],
        title='Tags (list[BaseModel])',
    )


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()
    ModelForm.from_item(AllTypes(), classes='w-full').render()


ui.run(title='02 — Field Types')
