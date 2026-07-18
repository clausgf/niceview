"""
# ModelGrid

Three variants of the AgGrid-based table component:

- **ModelGrid** — read-only display of a list
- **ModelGridInlineEdit** — per-cell editing with immediate validation and
  persistence; backed by an in-memory list here
- **ModelGridInlineEdit (JSON)** — same as above, but persists to a JSON file
  automatically after every change; the file is created on first run
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from typing import Literal
from nicegui import ui
from niceview import ModelGrid, ModelGridInlineEdit


class Task(pydantic.BaseModel):
    title: str = pydantic.Field(default='', max_length=40, title='Title')
    priority: Literal['low', 'medium', 'high'] = pydantic.Field(default='medium', title='Priority')
    done: bool = pydantic.Field(default=False, title='Done')


TASKS_PATH = Path('./example_tasks.json')

tasks = [
    Task(title='Buy groceries', priority='low', done=True),
    Task(title='Write report', priority='high', done=False),
    Task(title='Call dentist', priority='medium', done=False),
    Task(title='Fix bug #42', priority='high', done=False),
    Task(title='Review PR', priority='medium', done=True),
]


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    with ui.card().classes('w-full'):
        ui.label('ModelGrid — read-only').classes('text-h6')
        ModelGrid.from_list(Task, tasks).render().widget.classes('w-full')

    with ui.card().classes('w-full'):
        ui.label('ModelGridInlineEdit — in-memory').classes('text-h6')
        ui.label('Double-click a cell to edit it. Changes are persisted in memory only.').classes('text-small')
        grid = ModelGridInlineEdit.from_list(Task, tasks)
        grid.render().widget.classes('w-full')
        grid.on_change(lambda e: ui.notify(f'{e.field_name} → {e.new_value}'))

    with ui.card().classes('w-full'):
        ui.label(f'ModelGridInlineEdit — JSON file ({TASKS_PATH})').classes('text-h6')
        ModelGridInlineEdit.from_json(Task, TASKS_PATH).render().widget.classes('w-full')


ui.run(title='05 — ModelGrid')
