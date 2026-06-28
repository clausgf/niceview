"""
# ModelForm — Basic

Demonstrates `ModelForm` with a simple Pydantic model.

- `ModelForm.from_item()` creates a form from an in-memory object
- Edits are written back to the Python object after validation
- `on_change` is called after every successfully validated change
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui
from niceview.wrapper import EditFormWrapper


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
        wrapper = EditFormWrapper.from_item(person, title='Edit Person')

    change_log = ui.log(max_lines=10).classes('w-full h-32 mt-4')
    change_log.push('Change log:')
    wrapper.on_change(lambda e: change_log.push(
        f'{e.field_name}: {e.previous_value!r} → {e.value!r}'
    ))


ui.run(title='01 — ModelForm Basic')
