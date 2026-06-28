"""
# Reactive Grid — Auto-update via ObservableList

Demonstrates the difference between a grid backed by a **plain list** and one backed
by an **ObservableList**.

| | Plain `list` | `ObservableList` |
|---|---|---|
| Add / change **via adapter** | auto-updates grid ✓ | auto-updates grid ✓ |
| Add / change **directly** on the original list | grid stays stale ✗ | auto-updates grid ✓ |
| Change item attributes (e.g. `done`) | grid stays stale ✗ | grid stays stale ✗ |
| Grid edit (e.g. toggle `done`) | updates original list ✓ | updates original list ✓ |

If you create a grid usign `from_list`, the list adapter is created internally.

When the input is already an `ObservableList`, the adapter uses **the same object**, so direct mutations
on the original list propagate immediately to the grid. `update_rows()` or the refresh button always update the grid.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
from time import time
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui
from nicegui.observables import ObservableList

from niceview.dataadapter import ListAdapter
from niceview.wrapper import EditGridWrapper


class Task(pydantic.BaseModel):
    title: str = pydantic.Field(default='', title='Title')
    done: bool = pydantic.Field(default=False, title='Done')

    def __repr__(self) -> str:
        return f"Task('{self.title}', done={self.done})"


# ---------------------------------------------------------------------------
# Section A: plain list via ListAdapter
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


_blink_on = False
_last_blink_time = time()

def _fmt(original: list) -> str:
    global _blink_on, _last_blink_time
    if (time() - _last_blink_time) > 0.5:
        _blink_on = not _blink_on
        _last_blink_time = time()
    blink = '*' if _blink_on else ' '

    lines = [f"{blink} original list = adapter._items ({type(original).__name__}, {len(original)} items)"]
    lines += [f"  {r!r}" for r in original]
    return '\n'.join(lines)


@ui.page('/')
def page():
    with ui.tabs().classes('w-full') as tabs:
        tab_home = ui.tab('Documentation')
        tab_plain_list = ui.tab('Plain List')
        tab_observablelist = ui.tab('ObservableList')

    with ui.tab_panels(tabs, value=tab_home).classes('w-full') as panels:

        with ui.tab_panel(tab_home):
            ui.markdown(__doc__ or '')

        with ui.tab_panel(tab_plain_list):

            # --- A: plain list ---
            with ui.card().classes('w-full'):
                ui.markdown(
                    '**Plain list**: '
                    'Adapter CRUD mutations probagate, but direct mutations to the original list do **not**.'
                )

                wrapper_a = EditGridWrapper.from_adapter(
                    Task, plain_adapter, inline_edit=True, classes='w-full',
                    title='Tasks (Plain List)',
                )

                code_a = ui.code(_fmt(plain_tasks)).classes('w-full')
                ui.timer(1, lambda: code_a.set_content(_fmt(plain_tasks)))

                def add_via_plain_adapter():
                    n = len(list(plain_adapter._items)) + 1
                    plain_adapter.create(Task(title=f'Task A{n} (via adapter)'))

                def add_to_plain_list():
                    n = len(plain_tasks) + 1
                    plain_tasks.append(Task(title=f'Task A{n} (direct — grid not updated!)'))

                def toggle_first_plain():
                    if plain_tasks:
                        plain_tasks[0].done = not plain_tasks[0].done

                with ui.row():
                    ui.button('update_rows', on_click=wrapper_a.grid.update_rows).props('color=positive')
                    ui.button('Add via adapter (auto-update)', on_click=add_via_plain_adapter)
                    ui.button('Direct add to list (no grid update)', on_click=add_to_plain_list).props('color=secondary')
                    ui.button('Toggle first item (no grid update)', on_click=toggle_first_plain).props('color=accent')

        with ui.tab_panel(tab_observablelist):

            # --- B: ObservableList ---
            with ui.card().classes('w-full'):
                ui.markdown(
                    '**ObservableList**: '
                    'Both adapter CRUD **and** direct mutations to `obs_tasks` auto-update the grid. '
                    'Direct changes to list items, however, still require `update_rows()` or the refresh button.'
                )

                wrapper_b = EditGridWrapper.from_adapter(
                    Task, obs_adapter, inline_edit=True, classes='w-full',
                    title='Tasks (ObservableList)',
                )

                code_b = ui.code(_fmt(obs_tasks)).classes('w-full')
                ui.timer(1, lambda: code_b.set_content(_fmt(obs_tasks)))

                def add_via_obs_adapter():
                    n = len(obs_tasks) + 1
                    obs_adapter.create(Task(title=f'Task B{n} (via adapter)'))

                def add_to_obs_list():
                    n = len(obs_tasks) + 1
                    obs_tasks.append(Task(title=f'Task B{n} (direct — also auto-updates!)'))

                def toggle_first_obs():
                    if obs_tasks:
                        obs_tasks[0].done = not obs_tasks[0].done
                        #wrapper_b.grid.update_rows()  # still needed: attribute change ≠ list change

                with ui.row():
                    ui.button('update_rows', on_click=wrapper_b.grid.update_rows).props('color=positive')
                    ui.button('Add via adapter (auto-update)', on_click=add_via_obs_adapter)
                    ui.button('Add to ObservableList (auto-update)', on_click=add_to_obs_list).props('color=secondary')
                    ui.button('Toggle first item (no grid update)', on_click=toggle_first_obs).props('color=accent')


ui.run(title='08 — Reactive Grid')
