"""
# Reactive Grid — Auto-update via ObservableList

Demonstrates the difference between a grid backed by a **plain list** and one backed
by an **ObservableList**.

| | Plain `list` | `ObservableList` |
|---|---|---|
| Add / change **via adapter** | auto-updates grid ✓ | auto-updates grid ✓ |
| Add / change **directly** on the original list | grid stays stale ✗ | auto-updates grid ✓ |

`ListAdapter` always wraps its input in an `ObservableList` internally. When the input
is already an `ObservableList`, the adapter uses **the same object**, so direct mutations
on the original list propagate immediately to the grid without any explicit `update_rows()`.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui
from nicegui.observables import ObservableList

from niceview.dataadapter import ListAdapter
from niceview.modelgrid import ModelGrid


class Task(pydantic.BaseModel):
    title: str = pydantic.Field(default='', title='Title')
    done: bool = pydantic.Field(default=False, title='Done')

    def __repr__(self) -> str:
        return f"Task('{self.title}', done={self.done})"


# ---------------------------------------------------------------------------
# Section A: plain list
#   plain_adapter._items is a NEW ObservableList — a copy of plain_tasks.
#   Direct mutations on plain_tasks are invisible to the adapter and the grid.
# ---------------------------------------------------------------------------
plain_tasks: list[Task] = [
    Task(title='Buy groceries', done=True),
    Task(title='Write report', done=False),
]
plain_adapter = ListAdapter(Task, plain_tasks)


# ---------------------------------------------------------------------------
# Section B: ObservableList
#   obs_adapter._items IS obs_tasks (same object).
#   Direct mutations on obs_tasks propagate to the grid automatically.
# ---------------------------------------------------------------------------
obs_tasks: ObservableList = ObservableList([
    Task(title='Buy groceries', done=True),
    Task(title='Write report', done=False),
])
obs_adapter = ListAdapter(Task, obs_tasks)


def _fmt(original: list, adapter_items: list) -> str:
    if original is adapter_items:
        lines = [f"original list = adapter._items ({type(original).__name__}, {len(original)} items):"]
        lines += [f"  {r!r}" for r in original]
    else:
        lines = [f"original list ({type(original).__name__}, {len(original)} items):"]
        lines += [f"  {r!r}" for r in original]
        lines += ['', f"adapter._items (ObservableList, {len(adapter_items)} items):"]
        lines += [f"  {r!r}" for r in adapter_items]
    return '\n'.join(lines)


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    # --- A: plain list ---
    with ui.card().classes('w-full'):
        ui.label('A — Plain list').classes('text-h6')
        ui.markdown(
            'The adapter copies the plain list into an internal `ObservableList`. '
            'Adapter CRUD auto-updates the grid; direct mutations to the original list do **not**.'
        )

        grid_a = ModelGrid.from_adapter(Task, plain_adapter, classes='w-full')
        grid_a.render()

        code_a = ui.code(_fmt(plain_tasks, plain_adapter._items)).classes('w-full')

        def add_via_plain_adapter():
            n = len(list(plain_adapter._items)) + 1
            plain_adapter.create(Task(title=f'Task A{n} (via adapter)'))
            code_a.set_content(_fmt(plain_tasks, plain_adapter._items))

        def add_to_plain_list():
            n = len(plain_tasks) + 1
            plain_tasks.append(Task(title=f'Task A{n} (direct — grid not updated!)'))
            code_a.set_content(_fmt(plain_tasks, plain_adapter._items))

        def toggle_first_plain():
            if plain_tasks:
                plain_tasks[0].done = not plain_tasks[0].done
                grid_a.update_rows()  # explicit call needed: item attribute change ≠ list change
                code_a.set_content(_fmt(plain_tasks, plain_adapter._items))

        with ui.row():
            ui.button('Add via adapter (auto-update)', on_click=add_via_plain_adapter)
            ui.button('Add to original list (no grid update)', on_click=add_to_plain_list).props('color=warning')
            ui.button('Toggle first item (explicit update_rows)', on_click=toggle_first_plain).props('color=secondary')

    ui.separator()

    # --- B: ObservableList ---
    with ui.card().classes('w-full'):
        ui.label('B — ObservableList').classes('text-h6')
        ui.markdown(
            'The adapter receives an `ObservableList` and uses it directly. '
            'Both adapter CRUD **and** direct mutations to `obs_tasks` auto-update the grid.'
        )

        grid_b = ModelGrid.from_adapter(Task, obs_adapter, classes='w-full')
        grid_b.render()

        code_b = ui.code(_fmt(obs_tasks, obs_tasks)).classes('w-full')

        obs_tasks.on_change(lambda _: code_b.set_content(_fmt(obs_tasks, obs_tasks)))

        def add_via_obs_adapter():
            n = len(obs_tasks) + 1
            obs_adapter.create(Task(title=f'Task B{n} (via adapter)'))

        def add_to_obs_list():
            n = len(obs_tasks) + 1
            obs_tasks.append(Task(title=f'Task B{n} (direct — also auto-updates!)'))

        def toggle_first_obs():
            if obs_tasks:
                obs_tasks[0].done = not obs_tasks[0].done
                grid_b.update_rows()  # still needed: attribute change ≠ list change
                code_b.set_content(_fmt(obs_tasks, obs_tasks))

        with ui.row():
            ui.button('Add via adapter (auto-update)', on_click=add_via_obs_adapter)
            ui.button('Add to ObservableList (auto-update)', on_click=add_to_obs_list).props('color=positive')
            ui.button('Toggle first item (explicit update_rows)', on_click=toggle_first_obs).props('color=secondary')


ui.run(title='08 — Reactive Grid')
