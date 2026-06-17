"""
# ModelForm — Basic

Demonstrates `ModelForm` with a simple Pydantic model.

- `ModelForm.from_item()` creates a form from an in-memory object
- Edits are written back to the Python object after validation
- `on_change` is called after every successfully validated change
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui
from niceview.modelform import ModelForm


class Person(pydantic.BaseModel):
    name: str = pydantic.Field(default='Alice', max_length=30, title='Name')
    age: int = pydantic.Field(default=30, ge=0, le=120, title='Age')
    active: bool = pydantic.Field(default=True, title='Active')


person = Person()


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    form = ModelForm.from_item(person, title='Edit Person', classes='w-96')
    form.render()

    change_log = ui.log(max_lines=10).classes('w-full h-32 mt-4')
    form.on_change(lambda e: change_log.push(
        f'{e.field_name}: {e.old_value!r} → {e.new_value!r}'
    ))


ui.run(title='01 — ModelForm Basic')
