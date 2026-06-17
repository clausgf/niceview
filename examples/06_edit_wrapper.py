"""
# EditGridWrapper / EditFormWrapper

Wrappers that add CRUD buttons on top of a grid or form:

- **EditGridWrapper** — Add / Edit / Delete buttons above a `ModelGrid`;
  Add and Edit open a dialog with a `ModelForm`
- **EditFormWrapper** — Save / Cancel / Delete / Refresh buttons for a
  `ModelForm` backed by a `ListModelAdapter`
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from typing import Literal
from nicegui import ui
from niceview.dataadapter import ListModelAdapter
from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGrid
from niceview.modeledit import EditGridWrapper, EditFormWrapper


class Task(pydantic.BaseModel):
    title: str = pydantic.Field(default='', max_length=40, title='Title')
    priority: Literal['low', 'medium', 'high'] = pydantic.Field(default='medium', title='Priority')
    done: bool = pydantic.Field(default=False, title='Done')


tasks = [
    Task(title='Buy groceries', priority='low', done=True),
    Task(title='Write report', priority='high', done=False),
    Task(title='Fix bug #42', priority='high', done=False),
]


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.card().classes('w-full'):
        ui.label('EditGridWrapper').classes('text-h6')
        wrapper = EditGridWrapper(
            ModelGrid.from_list(Task, tasks),
            title='Tasks',
            add_button='Add', delete_button='Delete', refresh_button='',
        )
        wrapper.render()
        wrapper.on_change(lambda e: ui.notify(f'Changed: {e.item}'))

    with ui.card().classes('w-full'):
        ui.label('EditFormWrapper').classes('text-h6')
        adapter = ListModelAdapter(Task, tasks)
        key = adapter.key_from_item(tasks[0])
        form = ModelForm.from_adapter(Task, adapter, key, classes='w-96')
        EditFormWrapper(form).render()


ui.run(title='06 — Edit Wrappers')
