"""
# ModelForm — NiceGUI Binding

The left panel shows a `ModelForm`. The right panel uses NiceGUI's
`bind_text_from` / `bind_visibility_from` to display the same Python
object's fields live — they update whenever the form writes a validated
change back to the object.

`num++` / `num--` modify `user.num` directly, bypassing the form.
The bound label updates immediately; the form input does **not** — NiceView
does not (yet) support two-way binding from the object back into the widget.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui
from niceview.modelform import ModelForm


class User(pydantic.BaseModel):
    name: str = pydantic.Field(max_length=20, title='Name')
    age: int = pydantic.Field(ge=0, le=120, title='Age')
    num: int = pydantic.Field(default=0, title='Counter')
    active: bool = pydantic.Field(default=True, title='Active')


user = User(name='Alice', age=30)


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.row().classes('w-full items-start gap-8'):
        with ui.card():
            ui.label('Form').classes('text-h6')
            ModelForm.from_item(user, classes='w-80').render()

        with ui.card():
            ui.label('Bound values').classes('text-h6')
            ui.label('Name: ').bind_text_from(user, 'name', backward=lambda v: f'Name: {v}')
            ui.label('Age: ').bind_text_from(user, 'age', backward=lambda v: f'Age: {v}')
            ui.label('Counter: ').bind_text_from(user, 'num', backward=lambda v: f'Counter: {v}')
            ui.label('● active').bind_visibility_from(user, 'active')
            ui.label('○ inactive').bind_visibility_from(user, 'active', value=False)

            ui.separator()
            ui.label('Direct object mutation (bypasses form):').classes('text-caption')
            with ui.row():
                ui.button('Counter++', on_click=lambda: setattr(user, 'num', user.num + 1))
                ui.button('Counter--', on_click=lambda: setattr(user, 'num', user.num - 1))


ui.run(title='03 — Form Binding')
