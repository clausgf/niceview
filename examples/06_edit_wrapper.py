"""
# EditGridWrapper / EditFormWrapper

Wrappers that add CRUD buttons on top of a grid or form:

- **EditGridWrapper** — Add / Edit / Delete / Refresh buttons above a `ModelGrid`;
  Add and Edit open a popup dialog with a `ModelForm`.
- **EditFormWrapper** — Refresh / Cancel / Apply / Ok buttons alongside a `ModelForm`
  backed by any adapter. Refresh and Cancel reload from the adapter (discarding unsaved
  edits); Apply and Ok save to the adapter.

Both sections share the same in-memory `tasks` list. The JSON view below each widget
updates automatically via an `on_change` listener whenever data changes.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pydantic
from typing import Literal
from nicegui import ui
from niceview.dataadapter import ListModelAdapter
from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGrid
from niceview.modeledit import EditGridWrapper, EditFormWrapper

class Task(pydantic.BaseModel):
    title: str = pydantic.Field(default='', min_length=1, max_length=40, title='Title')
    priority: Literal['low', 'medium', 'high'] = pydantic.Field(default='medium', title='Priority')
    done: bool = pydantic.Field(default=False, title='Done')


t1 = Task(title='Buy groceries', priority='low', done=True)
tasks = [
    t1,
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
        )
        wrapper.render()
        data_grid = ui.code(str(tasks)).classes('w-full')
        wrapper.on_change(lambda e: data_grid.set_content(str(tasks)))

    with ui.card().classes('w-full'):
        ui.label('EditFormWrapper').classes('text-h6')
        adapter = ListModelAdapter(Task, tasks)
        key = adapter.key_from_item(tasks[0])
        form = ModelForm.from_adapter(Task, adapter, key, classes='w-96')
        EditFormWrapper(form).render()
        data_form = ui.code(str(t1)).classes('w-full')
        form.on_change(lambda e: data_form.set_content(str(t1)))


ui.run(title='06 — Edit Wrappers')
