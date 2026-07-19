"""
# Reactive Grid — Auto-update via ObservableList

Demonstrates the difference between a grid backed by a **plain list** and one backed
by an **ObservableList**.

| | Plain `list` | `ObservableList` |
|---|---|---|
| Add / delete **via adapter** | auto-updates grid ✓ | auto-updates grid ✓ |
| Add / delete **directly** on the original list | grid stays stale ✗ | auto-updates grid ✓ |
| Change item attributes (e.g. `done`) | grid stays stale ✗ | grid stays stale ✗ |
| Grid edit (e.g. toggle `done`) | updates original list ✓ | updates original list ✓ |

`ListAdapter` copies a plain list into an internal `ObservableList`, so direct
mutations on the original list are invisible to the grid. When the input already
**is** an `ObservableList`, the adapter uses the same object and direct mutations
propagate immediately. `update_rows()` or the Refresh button always work.
"""

import pydantic
from nicegui import ui
from nicegui.observables import ObservableList

from niceview import ListAdapter, EditGridWrapper


class Task(pydantic.BaseModel):
    title: str = pydantic.Field(default='', title='Title')
    done: bool = pydantic.Field(default=False, title='Done')

    def __repr__(self) -> str:
        return f"Task('{self.title}', done={self.done})"


plain_tasks: list[Task] = [Task(title='Buy groceries', done=True), Task(title='Write report')]
plain_adapter = ListAdapter(Task, plain_tasks)

obs_tasks: ObservableList = ObservableList([Task(title='Buy groceries', done=True), Task(title='Write report')])
obs_adapter = ListAdapter(Task, obs_tasks)


def _fmt(original: list) -> str:
    lines = [f'original list ({type(original).__name__}, {len(original)} items)']
    return '\n'.join(lines + [f'  {t!r}' for t in original])


def render_section(title: str, note: str, original: list, adapter: ListAdapter) -> None:
    with ui.card().classes('w-full'):
        ui.markdown(f'**{title}**: {note}')

        wrapper = EditGridWrapper.from_adapter(Task, adapter, inline_edit=True, title=title).render()
        wrapper.grid.widget.classes('w-full')  # canonical styling: via the exposed grid widget

        live_view = ui.code(_fmt(original)).classes('w-full')
        ui.timer(1, lambda: live_view.set_content(_fmt(original)))

        def add_via_adapter() -> None:
            adapter.create(Task(title=f'Task {len(original) + 1} (via adapter)'))

        def add_directly() -> None:
            original.append(Task(title=f'Task {len(original) + 1} (direct)'))

        def toggle_first() -> None:
            if original:
                original[0].done = not original[0].done  # attribute change: never auto-updates

        with ui.row():
            ui.button('update_rows', on_click=wrapper.grid.update_rows).props('color=positive')
            ui.button('Add via adapter', on_click=add_via_adapter)
            ui.button('Add directly to list', on_click=add_directly).props('color=secondary')
            ui.button('Toggle first item (stale)', on_click=toggle_first).props('color=accent')


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()
    render_section('Plain list', 'adapter mutations propagate, direct list mutations do **not**.',
                   plain_tasks, plain_adapter)
    render_section('ObservableList', 'adapter mutations **and** direct list mutations propagate; '
                   'attribute changes on items still need `update_rows()`.',
                   obs_tasks, obs_adapter)


ui.run(title='08 — Reactive Grid')
