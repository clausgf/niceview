"""
# ModelForm — Basic

Demonstrates `ModelForm` with a simple Pydantic model.

- `ModelForm.from_item()` creates a form from an in-memory object
- Edits are written back to the Python object after validation
- `on_change` is called after every successfully validated change
"""

import pydantic
from nicegui import ui
from niceview import ModelForm


class Person(pydantic.BaseModel):
    name: str = pydantic.Field(max_length=30, title='Name')
    age: int = pydantic.Field(ge=0, le=120, title='Age')
    active: bool = pydantic.Field(default=True, title='Active')


person = Person(name='Alice', age=30)


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.card():
        form = ModelForm.from_item(person)
        form.render()

    change_log = ui.log(max_lines=10).classes('w-full h-32 mt-4')
    change_log.push('Change log:')
    form.on_change(lambda e: change_log.push(
        f'{e.field_name}: {e.previous_value!r} → {e.value!r}'
    ))


ui.run(title='01 — ModelForm Basic')
