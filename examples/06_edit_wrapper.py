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

from time import time
import pydantic
from typing import Literal
from nicegui import ui
from niceview.dataadapter import ListAdapter
from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGrid, ModelGridInlineEdit
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


_blink_on = False
_last_blink_time = time()

def _fmt(original: list) -> str:
    global _blink_on, _last_blink_time
    if (time() - _last_blink_time) > 0.5:
        _blink_on = not _blink_on
        _last_blink_time = time()
    blink = '*' if _blink_on else ' '

    lines = [f"{blink} {type(original).__name__} ({len(original)} items)"]
    lines += [f"  {r!r}" for r in original]
    return '\n'.join(lines)


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.card().classes('w-full'):
        wrapper = EditGridWrapper(
            ModelGrid.from_list(Task, tasks),
            title='Tasks (EditGridWrapper with default buttons and dialogs)',
        )
        wrapper.render()

    with ui.card().classes('w-full'):
        ui.label('EditGridWrapper').classes('text-h6')
        wrapper = EditGridWrapper(
            ModelGridInlineEdit.from_list(Task, tasks),
            title='Tasks (EditGridWrapper with inline editing)',
        )
        wrapper.render()
    
    with ui.card().classes('w-full'):
        code_b = ui.code(_fmt(tasks)).classes('w-full')
        ui.timer(1, lambda: code_b.set_content(_fmt(tasks)))

    # with ui.card().classes('w-full'):
    #     ui.label('EditFormWrapper').classes('text-h6')
    #     adapter = ListAdapter(Task, tasks)
    #     key = adapter.key_from_item(tasks[0])
    #     form = ModelForm.from_adapter(Task, adapter, key, classes='w-96')
    #     EditFormWrapper(form).render()
    #     data_form = ui.code(str(t1)).classes('w-full')
    #     form.on_change(lambda e: data_form.set_content(str(t1)))


ui.run(title='06 — Edit Wrappers')
